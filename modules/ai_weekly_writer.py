from __future__ import annotations

import openai
import streamlit as st

import math

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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": WEEKLY_WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": input_content},
            ],
            temperature=0.7,
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

    def _sum_values(values):
        total = 0.0
        for val in _safe_dict(values).values():
            try:
                total += float(val or 0)
            except (TypeError, ValueError):
                continue
        return total

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

    def _format_number(value, suffix=""):
        number = _to_float(value)
        if number is None:
            return "-"
        formatted = f"{int(number)}" if number.is_integer() else f"{number:.1f}"
        return f"{formatted}{suffix}" if suffix else formatted

    def _format_breakdown(values, suffix):
        data = _safe_dict(values)
        if not data:
            return "-"
        order = ["일반식", "죽식", "다진식"]
        ordered_keys = [key for key in order if key in data] + [
            key for key in data
            if key not in order
        ]
        return " / ".join(f"{key} {_format_number(data.get(key), suffix)}" for key in ordered_keys)

    payload = _safe_dict(payload)
    prev_week = _safe_dict(payload.get("previous_week"))
    curr_week = _safe_dict(payload.get("current_week"))
    changes = _safe_dict(payload.get("changes"))
    per_attendance = _safe_dict(payload.get("per_attendance"))

    prev_meals = _safe_dict(prev_week.get("meals"))
    curr_meals = _safe_dict(curr_week.get("meals"))
    prev_toilet = _safe_dict(prev_week.get("toilet"))
    curr_toilet = _safe_dict(curr_week.get("toilet"))
    toilet_delta = _safe_dict(changes.get("toilet_breakdown"))

    meal_total_prev = _format_number(_sum_values(prev_meals), "회분")
    meal_total_curr = _format_number(_sum_values(curr_meals), "회분")
    toilet_total_prev = _format_number(_sum_values(prev_toilet), "회")
    toilet_total_curr = _format_number(_sum_values(curr_toilet), "회")
    meal_change = _format_number(changes.get("meal"), "회분")
    toilet_change = _format_number(changes.get("toilet"), "회")

    if toilet_delta:
        toilet_delta_summary = " / ".join(
            f"{label} {_format_number(toilet_delta.get(label), '회')}"
            for label in ("소변", "대변", "기저귀교환")
        )
    else:
        toilet_delta_summary = "-"

    meal_breakdown_curr = _format_breakdown(curr_meals, "회분")

    meal_avg_prev = _format_number(per_attendance.get("meal_avg_prev"), "회분")
    meal_avg_curr = _format_number(per_attendance.get("meal_avg_curr"), "회분")
    meal_avg_change_label = per_attendance.get("meal_avg_change_label") or "데이터 부족"
    toilet_avg_prev = _format_number(per_attendance.get("toilet_avg_prev"), "회")
    toilet_avg_curr = _format_number(per_attendance.get("toilet_avg_curr"), "회")
    toilet_avg_change_label = per_attendance.get("toilet_avg_change_label") or "데이터 부족"

    def _is_significant_percent(value: object, threshold: float) -> bool:
        num = _to_float(value)
        if num is None or not math.isfinite(num):
            return False
        return abs(num) >= threshold

    meal_avg_percent = per_attendance.get("meal_avg_percent")
    toilet_avg_percent = per_attendance.get("toilet_avg_percent")

    show_meal_avg = _is_significant_percent(meal_avg_percent, 10.0)
    show_toilet_avg = _is_significant_percent(toilet_avg_percent, 10.0)

    reference_metrics_block = ""
    if show_meal_avg or show_toilet_avg:
        lines = ["# [참고 지표(판단용/출력 금지)]"]
        if show_meal_avg:
            lines.append(
                f"- 식사량(출석일수 보정 평균): {meal_avg_prev} → {meal_avg_curr} ({meal_avg_change_label})"
            )
        if show_toilet_avg:
            lines.append(
                f"- 배설(출석일수 보정 평균): {toilet_avg_prev} → {toilet_avg_curr} ({toilet_avg_change_label})"
            )
        reference_metrics_block = "\n".join(lines)

    return WEEKLY_WRITER_USER_TEMPLATE.format(
        name=name,
        start_date=date_range[0].strftime("%Y-%m-%d"),
        end_date=date_range[1].strftime("%Y-%m-%d"),
        attendance_prev=prev_week.get("attendance", 0),
        attendance_curr=curr_week.get("attendance", 0),
        meal_total_prev=meal_total_prev,
        meal_total_curr=meal_total_curr,
        meal_change=meal_change,
        meal_avg_prev=meal_avg_prev,
        meal_avg_curr=meal_avg_curr,
        meal_avg_change_label=meal_avg_change_label,
        toilet_total_prev=toilet_total_prev,
        toilet_total_curr=toilet_total_curr,
        toilet_change=toilet_change,
        toilet_avg_prev=toilet_avg_prev,
        toilet_avg_curr=toilet_avg_curr,
        toilet_avg_change_label=toilet_avg_change_label,
        reference_metrics_block=reference_metrics_block,
        toilet_delta_summary=toilet_delta_summary,
        meal_breakdown_curr=meal_breakdown_curr,
        physical_prev=_safe_text(prev_week.get("physical")),
        cognitive_prev=_safe_text(prev_week.get("cognitive")),
        nursing_prev=_safe_text(prev_week.get("nursing")),
        functional_prev=_safe_text(prev_week.get("functional")),
        physical_curr=_safe_text(curr_week.get("physical")),
        cognitive_curr=_safe_text(curr_week.get("cognitive")),
        nursing_curr=_safe_text(curr_week.get("nursing")),
        functional_curr=_safe_text(curr_week.get("functional")),
    )
