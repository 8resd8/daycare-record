from __future__ import annotations

import openai
import streamlit as st

from prompts import WEEKLY_WRITER_SYSTEM_PROMPT, WEEKLY_WRITER_USER_TEMPLATE


def _get_openai_client() -> openai.OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API 키가 설정되어 있지 않습니다.")
    return openai.OpenAI(api_key=api_key)


def generate_weekly_report(customer_name, date_range, analysis_payload):
    input_content = _format_input_data(customer_name, date_range, analysis_payload)

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": WEEKLY_WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": input_content},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            return {"error": "AI 응답이 비어 있습니다."}
        return content.strip()
    except Exception as exc:
        return {"error": f"AI 생성 중 오류 발생: {exc}"}


def _format_input_data(name, date_range, payload) -> str:

    def _safe_dict(value):
        return value if isinstance(value, dict) else {}

    def _safe_text(value):
        text = str(value).strip() if value else ""
        return text or "없음"

    def _to_float(value):
        if value in (None, "", "-", "없음"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        for suffix in ("회분", "회"):
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
        text = text.replace(",", "")
        try:
            return float(text)
        except ValueError:
            return None

    def _trend_label(delta_value: object) -> str:
        value = _to_float(delta_value)
        if value is None:
            return "데이터 부족"
        if value > 0:
            return "증가"
        if value < 0:
            return "감소"
        return "유지"

    def _pick_line(text: str, index: int) -> str:
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        if not lines:
            return "없음"
        if 0 <= index < len(lines):
            return lines[index]
        return lines[-1]

    def _compose_oer(text: str, fallback: str) -> tuple[str, str, str]:
        if not text or str(text).strip() in ("", "없음", "-"):
            return fallback, "없음", "없음"
        clean = str(text).strip()
        return _pick_line(clean, 0), _pick_line(clean, 1), _pick_line(clean, 2)

    def _notes_trend(prev_text: str, curr_text: str) -> str:
        prev_clean = (prev_text or "").strip()
        curr_clean = (curr_text or "").strip()
        if not prev_clean and not curr_clean:
            return "변화 없음"
        if prev_clean == curr_clean:
            return "유지"
        return "유지"

    def _build_physical_change_observation(trend_meal: str, trend_toilet: str) -> str:
        for label, trend in (("식사", trend_meal), ("배설", trend_toilet)):
            if trend in ("증가", "감소"):
                return f"저번주에 비해 이번주 {label} 상태가 {trend}하였음"
        if trend_meal == "유지" and trend_toilet == "유지":
            return "저번주에 비해 이번주 신체 상태가 전반적으로 유지되었음"
        return "저번주에 비해 이번주 신체 상태의 변화 여부를 관찰하였음"

    payload = _safe_dict(payload)
    prev_week = _safe_dict(payload.get("previous_week"))
    curr_week = _safe_dict(payload.get("current_week"))
    changes = _safe_dict(payload.get("changes"))
    previous_weekly_report = _safe_text(payload.get("previous_weekly_report"))

    # Priority 1: Physical (신체활동 지원)
    physical_prev = _safe_text(prev_week.get("physical"))
    physical_curr = _safe_text(curr_week.get("physical"))
    
    # Priority 2: Cognitive (인지관리)
    cognitive_prev = _safe_text(prev_week.get("cognitive"))
    cognitive_curr = _safe_text(curr_week.get("cognitive"))
    
    # Priority 3: Previous Weekly Evaluation (저번주 주간 상태평가) - already loaded as previous_weekly_report
    
    # Priority 4: Nursing (간호관리)
    nursing_prev = _safe_text(prev_week.get("nursing"))
    nursing_curr = _safe_text(curr_week.get("nursing"))
    
    # Priority 5: Functional (기능회복)
    functional_prev = _safe_text(prev_week.get("functional"))
    functional_curr = _safe_text(curr_week.get("functional"))

    meal_trend = _trend_label(changes.get("meal"))
    toilet_trend = _trend_label(changes.get("toilet"))
    physical_trend = meal_trend if meal_trend != "유지" else toilet_trend
    cognitive_trend = _notes_trend(cognitive_prev, cognitive_curr)
    behavior_trend = _notes_trend(functional_prev, functional_curr)

    physical_observation, physical_evidence, _ = _compose_oer(
        physical_curr,
        _build_physical_change_observation(meal_trend, toilet_trend),
    )
    physical_bridge = _pick_line(physical_prev, 0)
    physical_intervention = _pick_line(nursing_curr, 0)

    cognitive_observation, cognitive_evidence, _ = _compose_oer(
        cognitive_curr,
        "지난주 대비 인지·심리 상태의 변화 여부를 관찰하였음",
    )
    cognitive_intervention = _pick_line(nursing_curr, 1)

    behavior_observation, behavior_evidence, _ = _compose_oer(
        functional_curr,
        "지난주 대비 행동·안전 상태의 변화 여부를 관찰하였음",
    )
    behavior_intervention = _pick_line(nursing_curr, 2)

    return WEEKLY_WRITER_USER_TEMPLATE.format(
        name=name,
        start_date=date_range[0].strftime("%Y-%m-%d"),
        end_date=date_range[1].strftime("%Y-%m-%d"),
        physical_trend=physical_trend,
        cognitive_trend=cognitive_trend,
        behavior_trend=behavior_trend,
        # Priority 1: Physical
        physical_prev=physical_prev,
        physical_curr=physical_curr,
        # Priority 2: Cognitive
        cognitive_prev=cognitive_prev,
        cognitive_curr=cognitive_curr,
        # Priority 3: Previous Weekly Evaluation
        previous_weekly_report=previous_weekly_report,
        # Priority 4: Nursing
        nursing_prev=nursing_prev,
        nursing_curr=nursing_curr,
        # Priority 5: Functional
        functional_prev=functional_prev,
        functional_curr=functional_curr,
    )
