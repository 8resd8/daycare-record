"""AI 품질 평가 탭 UI 모듈"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.db_connection import db_query
from modules.customers import resolve_customer_id
from modules.services.daily_report_service import evaluation_service
from modules.ui.ui_helpers import get_active_doc, get_active_person_records
from modules.repositories.ai_evaluation import AiEvaluationRepository


def render_ai_evaluation_tab():
    """AI 품질 평가 탭 렌더링"""
    doc_ctx, person_name, person_records = get_active_person_records()
    active_doc = doc_ctx or get_active_doc()

    if not active_doc:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 선택해주세요.")
    elif not person_records:
        st.warning("분석할 데이터가 없습니다.")
    else:
        st.markdown(f"### 📊 기록 품질 전수 조사 - {person_name or active_doc['name']}")

        st.divider()
        st.write("### 📝 새로운 평가 실행")

        grade_filter_new = st.selectbox(
            "등급 필터",
            options=["개선", "우수", "평균", "평가없음", "전체"],
            index=0,
            key="ai_grade_filter",
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            start_btn = st.button("🚀 전체 평가 시작", type="primary")

        if start_btn:
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(person_records)

            # Use the new evaluate_parsed_person method for in-memory data
            eval_results = {}
            
            for i, record in enumerate(person_records):
                date = record.get("date", "날짜 없음")
                status_text.text(f"🔍 {date} 기록 평가 중... ({i+1}/{total})")
                
                # Get customer_id first
                customer_id = resolve_customer_id(
                    name=record.get("customer_name", ""),
                    recognition_no=record.get("customer_recognition_no"),
                    birth_date=record.get("customer_birth_date")
                )
                
                if not customer_id:
                    st.warning(f"{record.get('customer_name', '')} 고객을 찾을 수 없습니다. 건너뜁니다.")
                    continue
                
                # Get record_id from database
                with db_query() as cursor:
                    cursor.execute(
                        "SELECT record_id FROM daily_infos WHERE customer_id=%s AND date=%s LIMIT 1",
                        (customer_id, date)
                    )
                    db_record = cursor.fetchone()
                    record_id = db_record["record_id"] if db_record else None
                
                if not record_id:
                    st.warning(f"{date} 기록을 DB에서 찾을 수 없습니다. 건너뜁니다.")
                    continue
                
                # Evaluate this record
                record_eval = {}
                writer = record.get("writer_physical") or record.get("writer_nursing") or record.get("writer_cognitive") or record.get("writer_recovery") or ""
                
                categories = [
                    ("PHYSICAL", record.get("physical_note", ""), record.get("writer_physical")),
                    ("COGNITIVE", record.get("cognitive_note", ""), record.get("writer_cognitive")),
                    ("NURSING", record.get("nursing_note", ""), record.get("writer_nursing")),
                    ("RECOVERY", record.get("functional_note", ""), record.get("writer_recovery"))
                ]
                
                for category, text, category_writer in categories:
                    note_writer_id = record.get(f"writer_{category.lower()}_id") or 1  # Default to 1 if not available
                    
                    result = evaluation_service.process_daily_note_evaluation(
                        record_id=record_id,
                        category=category,
                        note_text=text,
                        note_writer_user_id=note_writer_id,
                        writer=category_writer or writer,
                        customer_name=record.get("customer_name", ""),
                        date=date
                    )
                    
                    if result and result["evaluation"]:
                        record_eval[category.lower()] = result["evaluation"]
                
                if record_eval:
                    # Use person_name::date as key to avoid conflicts between people
                    person_name = record.get("customer_name", "미상")
                    eval_key = f"{person_name}::{date}"
                    eval_results[eval_key] = record_eval
                
                progress_bar.progress((i + 1) / total)
            
            if eval_results:
                # Store results in active_doc
                if "eval_results" not in active_doc:
                    active_doc["eval_results"] = {}
                active_doc["eval_results"].update(eval_results)
                
                # Update session_state
                for doc in st.session_state.docs:
                    if doc["id"] == active_doc["id"]:
                        doc["eval_results"] = active_doc["eval_results"]
                        break
            
            progress_bar.progress(1.0)
            status_text.text("✅ 분석 완료!")
            st.success("모든 평가가 완료되었습니다!")
            
            st.rerun()

        # AI 분석 리포트 섹션 - 평가 시작 전 원본 텍스트만 표시
        st.divider()
        st.write("### 📝 AI 분석 리포트")

        eval_tabs = st.tabs(["신체활동", "인지관리", "간호관리", "기능회복"])

        def show_original_df(category_key, note_key, writer_key):
            """평가 시작 전 원본 텍스트만 표시하는 함수"""
            rows = []
            for record in person_records:
                date = record.get("date", "")
                note_text = record.get(note_key, "")
                writer = record.get(writer_key, "")
                
                if note_text and note_text.strip() not in ['특이사항 없음', '결석', '']:
                    rows.append({
                        "날짜": date,
                        "작성자": writer,
                        "원본 내용": note_text,
                        "수정 제안": "",
                        "이유": ""
                    })
            
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("해당 카테고리의 기록이 없습니다.")

        def show_eval_df(category_key, note_key, writer_key):
            """평가 완료 후 결과를 표시하는 함수"""
            def _pick_item(res, key):
                if not res:
                    return {}
                if key in res and isinstance(res.get(key), dict):
                    return res.get(key) or {}
                alt_keys = {
                    "cognitive": ["cognition", "cognitve", "인지", "인지관리"],
                    "physical": ["phys", "신체", "신체활동"],
                    "nursing": ["nurse", "간호", "간호관리"],
                    "recovery": ["rehab", "functional", "기능", "기능회복"],
                }
                for k in alt_keys.get(key, []):
                    if k in res and isinstance(res.get(k), dict):
                        return res.get(k) or {}
                return {}

            rows = []
            for eval_key, res in active_doc["eval_results"].items():
                # Parse person_name::date format
                if "::" in eval_key:
                    _, date = eval_key.split("::", 1)
                else:
                    date = eval_key  # Fallback for old format

                item = _pick_item(res or {}, category_key)
                original_record = next((r for r in person_records if r["date"] == date), {})

                grade = item.get("grade_code", "-")
                # Convert English grade_code to Korean display
                grade_map = {
                    "EXCELLENT": "우수",
                    "NORMAL": "평균",
                    "IMPROVE": "개선",
                    "NONE": "평가없음"
                }
                # Handle both English and Korean inputs
                if grade in grade_map:
                    grade_display = grade_map[grade]
                else:
                    grade_display = grade if grade != "-" else "-"

                if grade_filter != "전체" and grade_display != grade_filter:
                    continue

                reason = item.get("reasoning_process", "")

                original_text = original_record.get(note_key, "")
                if not original_text:
                    original_text = item.get("original_sentence", "")

                rows.append({
                    "날짜": date,
                    "등급": grade_display,
                    "수정 제안": item.get("suggestion_text", ""),
                    "원본 내용": original_text,
                    "이유": reason,
                    "작성자": original_record.get(writer_key, "")
                })
            df = pd.DataFrame(rows)
            if df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                def _row_style(row):
                    if row["등급"] == "개선":
                        return ["color: green; font-weight: 600;"] * len(row)
                    return ["" for _ in row]

                def _grade_style(val):
                    if val == "개선":
                        return "color: green; font-weight: 600;"
                    if val == "우수":
                        return "color: blue; font-weight: 600;"
                    return ""
                styled = df.style.apply(_row_style, axis=1).map(_grade_style, subset=["등급"])
                st.dataframe(styled, use_container_width=True, hide_index=True)

        # 평가 결과가 있으면 평가 결과를, 없으면 원본 텍스트만 표시
        if active_doc.get("eval_results"):
            with eval_tabs[0]: show_eval_df("physical", "physical_note", "writer_phy")
            with eval_tabs[1]: show_eval_df("cognitive", "cognitive_note", "writer_cog")
            with eval_tabs[2]: show_eval_df("nursing", "nursing_note", "writer_nur")
            with eval_tabs[3]: show_eval_df("recovery", "functional_note", "writer_func")
        else:
            with eval_tabs[0]: show_original_df("physical", "physical_note", "writer_phy")
            with eval_tabs[1]: show_original_df("cognitive", "cognitive_note", "writer_cog")
            with eval_tabs[2]: show_original_df("nursing", "nursing_note", "writer_nur")
            with eval_tabs[3]: show_original_df("recovery", "functional_note", "writer_func")
