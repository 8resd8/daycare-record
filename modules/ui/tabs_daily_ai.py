"""AI 품질 평가 탭 UI 모듈"""

import pandas as pd
import streamlit as st

from modules.customers import resolve_customer_id
from modules.db_connection import db_query
from modules.services.daily_report_service import evaluation_service
from modules.ui.ui_helpers import get_active_doc, get_active_person_records


def render_ai_evaluation_tab():
    """AI 품질 평가 탭 렌더링"""
    doc_ctx, person_name, person_records = get_active_person_records()
    active_doc = doc_ctx or get_active_doc()

    if not active_doc:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 선택해주세요.")
    elif not person_records:
        st.warning("분석할 데이터가 없습니다.")
    else:
        st.markdown(f"### 장기요양급여 기록지 - {person_name or active_doc['name']}")

        # 필수 항목 체크 섹션
        # st.divider()
        
        def check_required_items(records):
            """필수 항목 체크 함수"""
            results = []
            
            for record in records:
                date = record.get("date", "")
                
                # "미이용", "결석", "일정없음"인 경우 모든 항목을 "해당없음"으로 처리
                # total_service_time 필드에서 상태 확인
                total_service = record.get("total_service_time", "").strip()
                is_absent = total_service in ["미이용", "결석", "일정없음"]
                
                # 종료시간 확인
                end_time = record.get("end_time", "")
                is_afternoon = False
                
                if end_time:
                    try:
                        # 시간 파싱 (예: "14:30")
                        hour_min = end_time.split(":")
                        if len(hour_min) >= 2:
                            hour = int(hour_min[0])
                            minute = int(hour_min[1])
                            # 17시 10분 이후이면 저녁 체크
                            is_afternoon = (hour > 17) or (hour == 17 and minute >= 10)
                    except:
                        pass
                
                # 작성 필수 항목 체크
                if is_absent:
                    # 모든 항목을 None으로 설정 (해당없음 표시)
                    checks = {
                        "날짜": date,
                        "총시간": None,
                        "시작시간": None,
                        "종료시간": None,
                        "이동서비스": None,
                    }
                else:
                    checks = {
                        "날짜": date,
                        "총시간": bool(record.get("total_service_time", "")),
                        "시작시간": bool(record.get("start_time", "")),
                        "종료시간": bool(end_time),
                        "이동서비스": bool(record.get("transport_service", "")),
                    }
                
                # 신체활동지원
                if is_absent:
                    physical_checks = {
                        "날짜": date,
                        "청결": None,
                        "점심": None,
                        "저녁": None,
                        "화장실": None,
                        "이동도움": None,
                        "특이사항": None
                    }
                else:
                    physical_checks = {
                        "날짜": date,
                        "청결": bool(record.get("hygiene_care", "")),
                        "점심": bool(record.get("meal_lunch", "")),
                        "저녁": bool(record.get("meal_dinner", "")) if is_afternoon else None,  # 15시 이후만 체크
                        "화장실": bool(record.get("toilet_care", "")),
                        "이동도움": bool(record.get("mobility_care", "")),
                        "특이사항": bool(record.get("physical_note", ""))
                    }
                
                # 인지관리
                if is_absent:
                    cognitive_checks = {
                        "날짜": date,
                        "인지관리": None,
                        "의사소통": None,
                        "특이사항": None
                    }
                else:
                    cognitive_checks = {
                        "날짜": date,
                        "인지관리": bool(record.get("cog_support", "")),
                        "의사소통": bool(record.get("comm_support", "")),
                        "특이사항": bool(record.get("cognitive_note", ""))
                    }
                
                # 건강및간호관리
                if is_absent:
                    health_checks = {
                        "날짜": date,
                        "혈압/체온": None,
                        "건강관리": None,
                        "특이사항": None
                    }
                else:
                    health_checks = {
                        "날짜": date,
                        "혈압/체온": bool(record.get("bp_temp", "")),
                        "건강관리": bool(record.get("health_manage", "")),
                        "특이사항": bool(record.get("nursing_note", ""))
                    }
                
                # 기능회복훈련
                if is_absent:
                    recovery_checks = {
                        "날짜": date,
                        "기본동작훈련": None,
                        "일상생활훈련": None,
                        "인지활동프로그램": None,
                        "인지기능향상": None,
                        "특이사항": None
                    }
                else:
                    recovery_checks = {
                        "날짜": date,
                        "기본동작훈련": bool(record.get("prog_basic", "")),
                        "일상생활훈련": bool(record.get("prog_activity", "")),
                        "인지활동프로그램": bool(record.get("prog_cognitive", "")),
                        "인지기능향상": bool(record.get("prog_therapy", "")),
                        "특이사항": bool(record.get("functional_note", ""))
                    }
                
                results.append({
                    "기본정보": checks,
                    "신체활동지원": physical_checks,
                    "인지관리": cognitive_checks,
                    "건강및간호관리": health_checks,
                    "기능회복훈련": recovery_checks
                })
            
            return results
        
        # 필수 항목 체크 실행
        check_results = check_required_items(person_records)
        
        if check_results:
            # 카테고리별 작성률 계산
            def calculate_completion_rate(results, category):
                """카테고리별 작성률 계산"""
                total_required = 0
                total_completed = 0
                
                for result in results:
                    checks = result[category]
                    for key, value in checks.items():
                        if key != "날짜" and value is not None:  # 해당없음 제외
                            total_required += 1
                            if value:
                                total_completed += 1
                
                if total_required == 0:
                    return 0, 0, 0
                
                percentage = (total_completed / total_required) * 100
                return percentage, total_completed, total_required

            # 작성률 표시
            st.write("#### 카테고리별 작성률")
            categories_korean = ["기본정보", "신체활동지원", "인지관리", "건강및간호관리", "기능회복훈련"]
            categories = ["기본정보", "신체활동지원", "인지관리", "건강및간호관리", "기능회복훈련"]

            rate_cols = st.columns(5)
            for idx, (col, cat_ko, cat) in enumerate(zip(rate_cols, categories_korean, categories)):
                percentage, completed, total = calculate_completion_rate(check_results, cat)
                with col:
                    # 100%가 아닐 때 주황색으로 표시
                    if percentage < 100:
                        st.markdown(f"<p style='color: gray; text-align: center; margin-bottom: 0px;'>{cat_ko}</p>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='color: orange; text-align: center; margin: 0px;'>{percentage:.1f}%</h3>", unsafe_allow_html=True)
                        st.markdown(f"<p style='color: gray; text-align: center; margin: 0px; font-size: 20px;'>{completed}/{total}</p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='color: gray; text-align: center; margin-bottom: 0px;'>{cat_ko}</p>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='color: black; text-align: center; margin: 0px;'>{percentage:.1f}%</h3>", unsafe_allow_html=True)
                        st.markdown(f"<p style='color: gray; text-align: center; margin: 0px; font-size: 20px;'>{completed}/{total}</p>", unsafe_allow_html=True)

            # 카테고리별 탭으로 표시
            category_tabs = st.tabs(categories_korean)

            for idx, category in enumerate(categories):
                with category_tabs[idx]:
                    # 테이블 생성
                    table_data = []
                    for result in check_results:
                        checks = result[category]
                        row = {"날짜": checks.get("날짜", "")}
                        
                        # 작성자 정보 추가
                        original_record = next((r for r in person_records if r["date"] == checks.get("날짜", "")), {})
                        
                        if category == "기본정보":
                            writers = [original_record.get("writer_phy"), original_record.get("writer_nur"), 
                                      original_record.get("writer_cog"), original_record.get("writer_func")]
                            row["작성자"] = next((w for w in writers if w), "")
                        elif category == "신체활동지원":
                            row["작성자"] = original_record.get("writer_phy") or ""
                        elif category == "인지관리":
                            row["작성자"] = original_record.get("writer_cog") or ""
                        elif category == "건강및간호관리":
                            row["작성자"] = original_record.get("writer_nur") or ""
                        elif category == "기능회복훈련":
                            row["작성자"] = original_record.get("writer_func") or ""

                        for key, value in checks.items():
                            if key != "날짜":
                                if value is None:
                                    row[key] = "해당없음"
                                elif value:
                                    row[key] = "✅"
                                else:
                                    row[key] = "❌"

                        table_data.append(row)

                    if table_data:
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("데이터가 없습니다.")

        st.divider()
        st.write("### 📝 특이사항 AI 평가 실행")

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
