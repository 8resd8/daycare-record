from __future__ import annotations

import gc
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

import json
from modules.repositories import WeeklyStatusRepository, DailyInfoRepository


def _optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """메모리 최적화된 DataFrame 반환

    - 문자열 컨럼을 category 타입으로 변환
    - 숫자 컨럼을 작은 dtype으로 변환
    """
    if df.empty:
        return df
    
    # 문자열 컨럼을 category로 변환 (중복이 많은 컨럼)
    category_candidates = [
        'meal_type', 'total_service_time', 'transport_service',
        'hygiene_care', 'mobility_care', 'cog_support', 'comm_support',
        'health_manage', 'nursing_manage', 'emergency',
        'prog_basic', 'prog_activity', 'prog_cognitive', 'prog_therapy'
    ]
    
    for col in category_candidates:
        if col in df.columns and df[col].dtype == 'object':
            # unique 값이 적으면 category로 변환
            if df[col].nunique() < len(df) * 0.5:
                df[col] = df[col].astype('category')
    
    return df

POSITIVE_KEYWORDS = ["개선", "안정", "호전", "유지", "활발", "양호", "미흡하지않음"]
NEGATIVE_KEYWORDS = ["악화", "저하", "불안", "통증", "문제", "감소", "주의", "거부", "통증"]
HIGHLIGHT_KEYWORDS = ["통증", "거부", "증가", "감소", "악화", "호전", "불안", "주의", "사고"]
MEAL_TYPES = ["일반식", "죽식", "다짐식", "경관식", "연식", "특식"]
C_WEEKDAYS = 7
MEAL_AMOUNT_RULES = [
    (["전량", "정량", "완", "모두", "잘"], (1.0, "전량")),
    (["절반", "1/2", "반", "50%", "이하"], (0.5, "1/2이하")),
    (["거부", "못", "불가", "0%"], (0.0, "거부")),
]
ABSENCE_STATUSES = {"미이용", "결석", "일정없음"}
CATEGORIES = {
    "physical": ("physical_note", "신체활동"),
    "cognitive": ("cognitive_note", "인지관리"),
    "nursing": ("nursing_note", "간호관리"),
    "functional": ("functional_note", "기능회복"),
}


def _score_text(text: Optional[str]) -> int:
    if not text:
        return 50
    normalized = text.replace(" ", "")
    score = 50
    for kw in POSITIVE_KEYWORDS:
        if kw in normalized:
            score += 5
    for kw in NEGATIVE_KEYWORDS:
        if kw in normalized:
            score -= 5
    return max(0, min(100, score))


def _fetch_two_week_records(
    name: str, start_date: date
) -> Tuple[List[Dict,], Tuple[date, date], Tuple[date, date]]:
    prev_start = start_date - timedelta(days=7)
    prev_end = start_date - timedelta(days=1)
    curr_end = start_date + timedelta(days=6)

    # DailyInfoRepository를 사용하여 고객 레코드 가져오기
    daily_info_repo = DailyInfoRepository()
    
    # 먼저 이름으로 고객 찾기
    from modules.repositories import CustomerRepository
    customer_repo = CustomerRepository()
    customer = customer_repo.find_by_name(name)
    
    if not customer:
        return [], (prev_start, prev_end), (start_date, curr_end)
    
    # 날짜 범위에 대한 레코드 가져오기
    records = daily_info_repo.get_customer_records(
        customer['customer_id'], 
        prev_start, 
        curr_end
    )
    
    # 예상 형식과 일치하도록 레코드 변환
    transformed_records = []
    for record in records:
        transformed_records.append({
            'date': record['date'],
            'total_service_time': record['total_service_time'],
            'physical_note': record['physical_note'],
            'cognitive_note': record['cognitive_note'],
            'nursing_note': record['nursing_note'],
            'functional_note': record['functional_note'],
            'meal_breakfast': record.get('meal_breakfast'),
            'meal_lunch': record.get('meal_lunch'),
            'meal_dinner': record.get('meal_dinner'),
            'toilet_care': record.get('toilet_care'),
            'bath_time': record.get('bath_time'),
            'bp_temp': record.get('bp_temp'),
            'prog_therapy': record.get('prog_therapy')
        })
    
    return transformed_records, (prev_start, prev_end), (start_date, curr_end)


def compute_weekly_status(customer_name: str, week_start_str: str, customer_id: int, 
                          use_cache: bool = True) -> Dict:
    """주간 상태 분석 (DB 캐싱 지원)
    
    Args:
        customer_name: 고객명
        week_start_str: 주 시작일 (YYYY-MM-DD)
        customer_id: 고객 ID
        use_cache: 캐시 사용 여부 (기본값: True)
    """
    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        aligned_start = week_start - timedelta(days=week_start.weekday())
    except Exception:
        return {"error": "날짜 형식이 올바르지 않습니다."}
    
    curr_end = aligned_start + timedelta(days=6)
    
    # 캐시 확인 (use_cache=True일 때)
    if use_cache and customer_id:
        cached = _load_cached_weekly_status(customer_id, aligned_start, curr_end)
        if cached:
            return cached

    try:
        rows, prev_range, curr_range = _fetch_two_week_records(customer_name, aligned_start)
    except Exception as e:
        return {"error": str(e)}

    if not rows:
        return {"data": [], "ranges": (prev_range, curr_range), "scores": {}}

    buckets: Dict[str, Dict[str, List[int]]] = {
        "prev": defaultdict(list),
        "curr": defaultdict(list),
    }

    for row in rows:
        record_date = row["date"]
        bucket = "curr" if record_date >= week_start else "prev"
        for key, (field, _) in CATEGORIES.items():
            buckets[bucket][key].append(_score_text(row.get(field)))

    def _avg(values: List[int]) -> Optional[float]:
        return round(mean(values), 1) if values else None

    scores = {}
    for key, (_, label) in CATEGORIES.items():
        prev_score = _avg(buckets["prev"].get(key, []))
        curr_score = _avg(buckets["curr"].get(key, []))
        if prev_score is None and curr_score is None:
            continue
        diff = None
        trend = "변화 없음"
        if prev_score is not None and curr_score is not None:
            diff = round(curr_score - prev_score, 1)
            if diff > 1:
                trend = "상승 ⬆️"
            elif diff < -1:
                trend = "하락 ⬇️"
        elif curr_score is not None:
            trend = "신규 데이터"
        scores[key] = {
            "label": label,
            "prev": prev_score,
            "curr": curr_score,
            "diff": diff,
            "trend": trend,
        }

    trend = analyze_weekly_trend(rows, prev_range, curr_range, customer_id)

    result = {
        "ranges": (prev_range, curr_range),
        "scores": scores,
        "raw": rows,
        "trend": trend,
    }
    
    # 결과 캐싱 (customer_id가 있을 때만)
    if customer_id:
        _save_weekly_status_cache(customer_id, aligned_start, curr_end, result)
    
    return result


def _load_cached_weekly_status(customer_id: int, start_date: date, end_date: date) -> Optional[Dict]:
    """캐시된 주간 분석 결과 로드"""
    try:
        repo = WeeklyStatusRepository()
        cached_text = repo.load_weekly_status(customer_id, start_date, end_date)
        if cached_text:
            cached = json.loads(cached_text)
            # ranges를 date 객체로 복원
            if 'ranges' in cached:
                prev_range, curr_range = cached['ranges']
                cached['ranges'] = (
                    (datetime.strptime(prev_range[0], '%Y-%m-%d').date(),
                     datetime.strptime(prev_range[1], '%Y-%m-%d').date()),
                    (datetime.strptime(curr_range[0], '%Y-%m-%d').date(),
                     datetime.strptime(curr_range[1], '%Y-%m-%d').date())
                )
            # raw의 date도 복원
            if 'raw' in cached:
                for row in cached['raw']:
                    if 'date' in row and isinstance(row['date'], str):
                        row['date'] = datetime.strptime(row['date'], '%Y-%m-%d').date()
            return cached
    except Exception:
        pass
    return None


def _save_weekly_status_cache(customer_id: int, start_date: date, end_date: date, result: Dict):
    """주간 분석 결과 캐싱"""
    try:
        # JSON 직렬화를 위해 date 객체 변환
        cache_data = result.copy()
        if 'ranges' in cache_data:
            prev_range, curr_range = cache_data['ranges']
            cache_data['ranges'] = (
                (prev_range[0].isoformat(), prev_range[1].isoformat()),
                (curr_range[0].isoformat(), curr_range[1].isoformat())
            )
        if 'raw' in cache_data:
            cache_data['raw'] = [
                {**row, 'date': row['date'].isoformat() if hasattr(row.get('date'), 'isoformat') else row.get('date')}
                for row in cache_data['raw']
            ]
        
        repo = WeeklyStatusRepository()
        repo.save_weekly_status(customer_id, start_date, end_date, json.dumps(cache_data, ensure_ascii=False))
    except Exception:
        pass  # 캐시 저장 실패는 무시


def _detect_meal_type(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for t in MEAL_TYPES:
        if t in text:
            return t
    return None


def _score_meal_amount(text: Optional[str]) -> float:
    if not text:
        return 0.75
    for keywords, (score, _) in MEAL_AMOUNT_RULES:
        if any(k in text for k in keywords):
            return score
    return 0.75


def _meal_amount_label(text: Optional[str]) -> str:
    if not text:
        return "정보없음"
    for keywords, (_, label) in MEAL_AMOUNT_RULES:
        if any(k in text for k in keywords):
            return label
    return "정보없음"


def _extract_toilet_count(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    matches = re.findall(r"(\d+)\s*회", text)
    if matches:
        nums = [int(n) for n in matches]
        return sum(nums)
    digits = re.findall(r"\d+", text)
    if digits:
        return float(digits[0])
    return None


def _parse_toilet_breakdown(text: Optional[str]) -> Dict[str, float]:
    if not text:
        return {}
    detail = {"stool": 0.0, "urine": 0.0, "diaper": 0.0}
    stool_matches = re.findall(r"(대변|배변)\s*(\d+)\s*회", text)
    urine_matches = re.findall(r"(소변|배뇨)\s*(\d+)\s*회", text)
    diaper_matches = re.findall(r"(기저귀|교환)\s*(\d+)\s*회", text)
    for _, n in stool_matches:
        detail["stool"] += float(n)
    for _, n in urine_matches:
        detail["urine"] += float(n)
    for _, n in diaper_matches:
        detail["diaper"] += float(n)
    return detail


def _summarize_meal_details(df: pd.DataFrame) -> str:
    """itertuples() 사용으로 성능 최적화"""
    if df.empty:
        return "-"
    details = []
    sorted_df = df.sort_values("date")
    for row in sorted_df.itertuples(index=False):
        detail = getattr(row, 'meal_detail', None)
        if detail:
            details.append(detail)
    return " / ".join(details) if details else "-"


def _summarize_toilet_summary(df: pd.DataFrame) -> str:
    if df.empty:
        return "-"
    total = {"stool": 0.0, "urine": 0.0, "diaper": 0.0}
    for detail_map in df["toilet_detail"]:
        if isinstance(detail_map, dict):
            for key in total:
                total[key] += detail_map.get(key, 0.0)
    if not any(total.values()):
        return "-"
    return (
        f"대변{int(total['stool'])}회/소변{int(total['urine'])}회 "
        f"(기저귀교환{int(total['diaper'])}회)"
    )


def _merge_notes(df: pd.DataFrame, highlight: bool = False) -> List[str]:
    """itertuples() 사용으로 성능 최적화"""
    notes = []
    # itertuples()는 iterrows()보다 10배 이상 빠름
    for row in df.itertuples(index=False):
        parts = []
        physical_note = getattr(row, 'physical_note', None)
        cognitive_note = getattr(row, 'cognitive_note', None)
        nursing_note = getattr(row, 'nursing_note', None)
        functional_note = getattr(row, 'functional_note', None)
        row_date = getattr(row, 'date', None)
        
        if physical_note:
            parts.append(f"신체: {physical_note}")
        if cognitive_note:
            parts.append(f"인지: {cognitive_note}")
        if nursing_note:
            parts.append(f"간호: {nursing_note}")
        if functional_note:
            parts.append(f"기능: {functional_note}")
        if not parts:
            continue
        line = f"[{row_date.strftime('%m-%d')}] " + " / ".join(parts)
        if highlight:
            for kw in HIGHLIGHT_KEYWORDS:
                if kw in line:
                    line = line.replace(
                        kw, f"<span style='background-color:#fff3cd;'>{kw}</span>"
                    )
        notes.append(line)
    return notes


def analyze_weekly_trend(
    rows: List[Dict], prev_range: Tuple[date, date], curr_range: Tuple[date, date], customer_id: int
) -> Dict:
    """DataFrame 최적화 버전 - 메모리 효율화"""
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    df["date"] = pd.to_datetime(df["date"]).dt.date
    
    # 메모리 최적화: category 타입 적용
    df = _optimize_dataframe(df)

    def _derive(row):
        meals = [row.get("meal_breakfast"), row.get("meal_lunch"), row.get("meal_dinner")]
        meal_types = [t for t in (_detect_meal_type(m) for m in meals) if t]
        meal_type = meal_types[0] if meal_types else "미확인"
        meal_scores = [_score_meal_amount(m or "") for m in meals if m is not None]
        meal_amount_score = round(sum(meal_scores) / len(meal_scores), 2) if meal_scores else 0.0
        meal_detail = []
        for meal_text in meals:
            if not meal_text:
                continue
            meal_detail.append(f"{_detect_meal_type(meal_text) or '미확인'} ({_meal_amount_label(meal_text)})")
        toilet_count = _extract_toilet_count(row.get("toilet_care"))
        toilet_detail = _parse_toilet_breakdown(row.get("toilet_care"))
        return pd.Series(
            {
                "meal_type": meal_type,
                "meal_amount_score": meal_amount_score,
                "toilet_count": toilet_count,
                "note_phy": row.get("physical_note"),
                "note_nur": row.get("nursing_note"),
                "meal_detail": " / ".join(meal_detail),
                "toilet_detail": toilet_detail,
            }
        )

    derived = df.apply(_derive, axis=1)
    df = pd.concat([df, derived], axis=1)

    prev_start, prev_end = prev_range
    curr_start, curr_end = curr_range
    last_week_df = df[
        (df["date"] >= prev_start)
        & (df["date"] <= prev_end)
    ]
    this_week_df = df[
        (df["date"] >= curr_start)
        & (df["date"] <= curr_end)
    ]

    def _mode(series: pd.Series) -> str:
        if series.empty:
            return "-"
        mode = series.mode()
        return mode.iloc[0] if not mode.empty else "-"

    last_type = _mode(last_week_df["meal_type"])
    this_type = _mode(this_week_df["meal_type"])

    notes = {
        "last": _merge_notes(last_week_df),
        "this": _merge_notes(this_week_df, highlight=True),
    }

    meal_detail_summary = {
        "last": _summarize_meal_details(last_week_df),
        "this": _summarize_meal_details(this_week_df),
    }
    toilet_detail_summary = {
        "last": _summarize_toilet_summary(last_week_df),
        "this": _summarize_toilet_summary(this_week_df),
    }

    def _collect_category_entries(source_df: pd.DataFrame) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for key, (field, label) in CATEGORIES.items():
            result[key] = [
                f"[{row['date'].strftime('%m-%d')}] {row[field]}"
                for _, row in source_df.iterrows()
                if row.get(field)
            ]
        return result

    last_category_entries = _collect_category_entries(last_week_df)
    this_category_entries = _collect_category_entries(this_week_df)

    category_notes = {}
    for key, (field, label) in CATEGORIES.items():
        category_notes[key] = {"label": label, "entries": this_category_entries.get(key, [])}

    def _format_entry_list(entries: List[str]) -> str:
        return "\n".join(entries) if entries else "없음"

    def _build_week_summary(
        entries: Dict[str, List[str]],
        attendance: int,
        meal_values: Dict[str, float],
        toilet_values: Dict[str, float],
    ) -> Dict[str, object]:
        return {
            "physical": _format_entry_list(entries.get("physical", [])),
            "cognitive": _format_entry_list(entries.get("cognitive", [])),
            "nursing": _format_entry_list(entries.get("nursing", [])),
            "functional": _format_entry_list(entries.get("functional", [])),
            "attendance": attendance,
            "meals": {
                "일반식": meal_values["일반식"],
                "죽식": meal_values["죽식"],
                "다진식": meal_values["다진식"],
            },
            "toilet": {
                "소변": toilet_values["urine"],
                "대변": toilet_values["stool"],
                "기저귀교환": toilet_values["diaper"],
            },
        }

    def _latest_text_value(source_df: pd.DataFrame, column: str) -> str:
        if source_df.empty or column not in source_df:
            return "-"
        values = [
            str(value).strip()
            for value in source_df[column]
            if value is not None and str(value).strip()
        ]
        return values[-1] if values else "-"

    MEAL_TYPE_KEYWORDS = {
        "일반식": ["일반식"],
        "죽식": ["죽식"],
        "다진식": ["다진식", "다짐식"],
    }

    MEAL_PORTION_MAP = {
        "1/2이상": 0.75,
        "1/2 이상": 0.75,
        "1/2이하": 0.25,
        "1/2 이하": 0.25,
        "정량": 1.0,
        "전량": 1.0,
        "완식": 1.0,
    }

    def _extract_meal_type_amounts(text: Optional[str]) -> Dict[str, float]:
        totals = {key: 0.0 for key in MEAL_TYPE_KEYWORDS}
        if not text:
            return totals
        segments = [seg.strip() for seg in re.split(r"[\/,]", text) if seg.strip()]
        for segment in segments:
            ratio = 0.5
            for keyword, value in MEAL_PORTION_MAP.items():
                if keyword in segment:
                    ratio = value
                    break
            matched = False
            for type_label, keywords in MEAL_TYPE_KEYWORDS.items():
                if any(keyword in segment for keyword in keywords):
                    totals[type_label] += ratio
                    matched = True
            if not matched and "일반식" in segment:
                totals["일반식"] += ratio
        return totals

    def _average_toilet_breakdown(source_df: pd.DataFrame) -> Optional[Dict[str, float]]:
        if source_df.empty:
            return None
        total = {"stool": 0.0, "urine": 0.0, "diaper": 0.0}
        count = 0
        for detail in source_df.get("toilet_detail", []):
            if not isinstance(detail, dict):
                continue
            count += 1
            for key in total:
                total[key] += detail.get(key, 0.0)
        if count == 0:
            return None
        return {key: round(total[key] / count, 1) for key in total}

    def _format_toilet_value(detail: Optional[Dict[str, float]], key: str) -> str:
        if not detail:
            return "-"
        value = detail.get(key)
        if value is None:
            return "-"
        if float(value).is_integer():
            formatted = f"{int(value)}"
        else:
            formatted = f"{value:.1f}"
        return f"{formatted}회"

    def _sum_toilet_counts(source_df: pd.DataFrame) -> Dict[str, float]:
        total = {"stool": 0.0, "urine": 0.0, "diaper": 0.0}
        for detail in source_df.get("toilet_detail", []):
            if not isinstance(detail, dict):
                continue
            for key in total:
                total[key] += detail.get(key, 0.0)
        return total

    def _format_total(value: float) -> str:
        if value is None:
            return "-"
        if float(value).is_integer():
            return f"{int(value)}"
        return f"{value:.1f}"

    def _sum_meals(source_df: pd.DataFrame) -> Dict[str, float]:
        totals = {key: 0.0 for key in MEAL_TYPE_KEYWORDS}
        meal_fields = ["meal_breakfast", "meal_lunch", "meal_dinner"]
        for _, row in source_df.iterrows():
            for field in meal_fields:
                parsed = _extract_meal_type_amounts(row.get(field))
                for meal_type, value in parsed.items():
                    totals[meal_type] += value
        return totals

    def _is_attended(total_service_time: Optional[str]) -> bool:
        if not total_service_time:
            return False
        normalized = str(total_service_time).strip()
        return normalized not in ABSENCE_STATUSES

    def _count_attendance(source_df: pd.DataFrame) -> int:
        if source_df.empty or "total_service_time" not in source_df:
            return 0
        return sum(
            1
            for value in source_df["total_service_time"]
            if _is_attended(value)
        )

    last_toilet_totals = _sum_toilet_counts(last_week_df)
    this_toilet_totals = _sum_toilet_counts(this_week_df)
    last_meals = _sum_meals(last_week_df)
    this_meals = _sum_meals(this_week_df)
    attendance_prev = _count_attendance(last_week_df)
    attendance_curr = _count_attendance(this_week_df)

    def _sum_totals(values: Dict[str, float]) -> float:
        return sum(values.values())

    last_meal_total = _sum_totals(last_meals)
    this_meal_total = _sum_totals(this_meals)
    last_toilet_total = _sum_totals(last_toilet_totals)
    this_toilet_total = _sum_totals(this_toilet_totals)

    def _ratio(total: float, count: int) -> Optional[float]:
        if count <= 0:
            return None
        return total / count

    meal_ratio_prev = _ratio(last_meal_total, attendance_prev)
    meal_ratio_curr = _ratio(this_meal_total, attendance_curr)
    toilet_ratio_prev = _ratio(last_toilet_total, attendance_prev)
    toilet_ratio_curr = _ratio(this_toilet_total, attendance_curr)

    def _percent_change(prev: Optional[float], curr: Optional[float]) -> Optional[float]:
        if prev is None or prev == 0 or curr is None:
            return None
        return round((curr - prev) / prev * 100, 1)

    meal_percent_change = _percent_change(meal_ratio_prev, meal_ratio_curr)
    toilet_percent_change = _percent_change(toilet_ratio_prev, toilet_ratio_curr)

    def _change_label(percent: Optional[float]) -> str:
        if percent is None:
            return "데이터 부족"
        if percent > 0:
            return f"{percent:.1f}% 상승"
        if percent < 0:
            return f"{abs(percent):.1f}% 하락"
        return "변화 없음"

    def _format_attendance_summary(
        entries: Dict[str, List[str]],
        attendance: int,
        meal_values: Dict[str, float],
        toilet_values: Dict[str, float],
    ) -> Dict[str, object]:
        def _format_entries(key: str) -> str:
            items = entries.get(key, [])
            return "\n".join(items) if items else "없음"

        return {
            "physical": _format_entries("physical"),
            "cognitive": _format_entries("cognitive"),
            "nursing": _format_entries("nursing"),
            "functional": _format_entries("functional"),
            "attendance": attendance,
            "meals": {
                "일반식": meal_values["일반식"],
                "죽식": meal_values["죽식"],
                "다진식": meal_values["다진식"],
            },
            "toilet": {
                "소변": toilet_values["urine"],
                "대변": toilet_values["stool"],
                "기저귀교환": toilet_values["diaper"],
            },
        }

    def _calc_total_meal(values: Dict[str, float]) -> float:
        return sum(values.values())

    change_payload = {
        "meal": _format_total(this_meal_total - last_meal_total) if last_meal_total is not None else "-",
        "toilet": _format_total(this_toilet_total - last_toilet_total) if last_toilet_total is not None else "-",
        "toilet_breakdown": {
            "소변": _format_total(this_toilet_totals["urine"] - last_toilet_totals["urine"]),
            "대변": _format_total(this_toilet_totals["stool"] - last_toilet_totals["stool"]),
            "기저귀교환": _format_total(this_toilet_totals["diaper"] - last_toilet_totals["diaper"]),
        },
    }

    # AI 참조용 이전 주간 보고서 로드 (리포지토리 사용)
    weekly_status_repo = WeeklyStatusRepository()
    previous_weekly_report = weekly_status_repo.load_weekly_status(
        customer_id=customer_id,
        start_date=prev_range[0],
        end_date=prev_range[1],
    )

    ai_payload = {
        "current_week": _format_attendance_summary(
            this_category_entries, attendance_curr, this_meals, this_toilet_totals
        ),
        "previous_week": _format_attendance_summary(
            last_category_entries, attendance_prev, last_meals, last_toilet_totals
        ),
        "per_attendance": {
            "meal_avg_prev": meal_ratio_prev,
            "meal_avg_curr": meal_ratio_curr,
            "meal_avg_change_label": _change_label(meal_percent_change),
            "meal_avg_percent": meal_percent_change,
            "toilet_avg_prev": toilet_ratio_prev,
            "toilet_avg_curr": toilet_ratio_curr,
            "toilet_avg_change_label": _change_label(toilet_percent_change),
            "toilet_avg_percent": toilet_percent_change,
        },
        "changes": change_payload,
        "previous_weekly_report": previous_weekly_report or "없음",
    }

    weekly_table = [
        {
            "주간": "저번주",
            "출석일": attendance_prev,
            "식사량(일반식)": _format_total(last_meals["일반식"]),
            "식사량(죽식)": _format_total(last_meals["죽식"]),
            "식사량(다진식)": _format_total(last_meals["다진식"]),
            "소변": f"{_format_total(last_toilet_totals['urine'])}회",
            "대변": f"{_format_total(last_toilet_totals['stool'])}회",
            "기저귀교환": f"{_format_total(last_toilet_totals['diaper'])}회",
        },
        {
            "주간": "이번주",
            "출석일": attendance_curr,
            "식사량(일반식)": _format_total(this_meals["일반식"]),
            "식사량(죽식)": _format_total(this_meals["죽식"]),
            "식사량(다진식)": _format_total(this_meals["다진식"]),
            "소변": f"{_format_total(this_toilet_totals['urine'])}회",
            "대변": f"{_format_total(this_toilet_totals['stool'])}회",
            "기저귀교환": f"{_format_total(this_toilet_totals['diaper'])}회",
        },
    ]

    header = {
        "meal_amount": {
            "label": "식사량",
            "prev": meal_ratio_prev,
            "curr": meal_ratio_curr,
            "change_label": _change_label(meal_percent_change),
            "percent": meal_percent_change,
        },
        "toilet": {
            "label": "배설",
            "prev": toilet_ratio_prev,
            "curr": toilet_ratio_curr,
            "change_label": _change_label(toilet_percent_change),
            "percent": toilet_percent_change,
        },
    }

    return {
        "header": header,
        "notes": notes,
        "meal_detail": meal_detail_summary,
        "toilet_detail": toilet_detail_summary,
        "weekly_table": weekly_table,
        "category_notes": category_notes,
        "ai_payload": ai_payload,
    }
