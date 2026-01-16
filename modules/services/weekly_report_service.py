"""주간 보고서 서비스 - 주간 상태변화 기록지 생성 비즈니스 로직"""

from typing import Dict, Tuple, Any, Optional
from datetime import date
from modules.clients.weekly_prompt import WEEKLY_WRITER_SYSTEM_PROMPT, WEEKLY_WRITER_USER_TEMPLATE
from modules.clients.ai_client import get_ai_client


class ReportService:
    """주간 보고서 서비스 클래스"""
    
    def generate_weekly_report(self, customer_name: str, date_range: Tuple[date, date], 
                              analysis_payload: Dict) -> str | Dict[str, str]:
        """주간 보고서 생성
        
        Args:
            customer_name: 고객명
            date_range: (시작일, 종료일) 튜플
            analysis_payload: 분석 데이터
            
        Returns:
            생성된 보고서 텍스트 또는 에러 딕셔너리
        """
        input_content = self._format_input_data(customer_name, date_range, analysis_payload)
        
        try:
            ai_client = get_ai_client(provider='openai')
            response = ai_client.chat_completion(
                model="gpt-4o-mini",
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
    
    def _format_input_data(self, name: str, date_range: Tuple[date, date], 
                          payload: Dict) -> str:
        """AI 입력 데이터 포맷팅
        
        Args:
            name: 고객명
            date_range: 날짜 범위
            payload: 분석 페이로드
            
        Returns:
            포맷된 입력 텍스트
        """
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
        
        def _trend_label(delta_value: Any) -> str:
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
        
        def _compose_oer(text: str, fallback: str) -> Tuple[str, str, str]:
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
        
        # 우선순위 1: 신체활동 지원
        physical_prev = _safe_text(prev_week.get("physical"))
        physical_curr = _safe_text(curr_week.get("physical"))
        
        # 우선순위 2: 인지관리
        cognitive_prev = _safe_text(prev_week.get("cognitive"))
        cognitive_curr = _safe_text(curr_week.get("cognitive"))
        
        meal_trend = _trend_label(changes.get("meal"))
        toilet_trend = _trend_label(changes.get("toilet"))
        physical_trend = meal_trend if meal_trend != "유지" else toilet_trend
        cognitive_trend = _notes_trend(cognitive_prev, cognitive_curr)
        
        physical_observation, physical_evidence, _ = _compose_oer(
            physical_curr,
            _build_physical_change_observation(meal_trend, toilet_trend),
        )
        physical_bridge = _pick_line(physical_prev, 0)
        
        cognitive_observation, cognitive_evidence, _ = _compose_oer(
            cognitive_curr,
            "지난주 대비 인지·심리 상태의 변화 여부를 관찰하였음",
        )
        
        return WEEKLY_WRITER_USER_TEMPLATE.format(
            name=name,
            start_date=date_range[0].strftime("%Y-%m-%d"),
            end_date=date_range[1].strftime("%Y-%m-%d"),
            physical_prev=physical_prev,
            physical_curr=physical_curr,
            cognitive_prev=cognitive_prev,
            cognitive_curr=cognitive_curr,
        )


# 서비스 인스턴스 생성
report_service = ReportService()
