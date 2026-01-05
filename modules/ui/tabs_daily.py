"""AI 품질 평가 탭 UI 모듈"""

import pandas as pd
import streamlit as st

from modules.customers import resolve_customer_id
from modules.db_connection import db_query
from modules.services.daily_report_service import evaluation_service
from modules.ui.ui_helpers import get_active_doc, get_active_person_records
from modules.repositories.ai_evaluation import AiEvaluationRepository
from modules.repositories.employee_evaluation import EmployeeEvaluationRepository
from modules.utils.enums import CategoryType, CategoryDisplay, RequiredFields, WriterFields, OptionalFields
from datetime import date
import time


def render_ai_evaluation_tab():
    """AI 품질 평가 탭 렌더링"""
    doc_ctx, person_name, person_records = get_active_person_records()
    active_doc = doc_ctx or get_active_doc()

    if not active_doc:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 선택해주세요.")
        return
    
    # 고객이 변경되었는지 확인하고 세션 상태 초기화
    current_customer_key = f"{active_doc.get('name', '')}_{active_doc.get('id', '')}"
    previous_customer_key = st.session_state.get('last_customer_key', '')
    
    if current_customer_key != previous_customer_key:
        # 고객이 변경되면 평가 결과 초기화
        st.session_state.special_note_eval_results = []
        st.session_state.last_customer_key = current_customer_key
        print(f"DEBUG: 고객 변경됨 - 이전: {previous_customer_key}, 현재: {current_customer_key}")
    
    if not person_records:
        st.warning("분석할 데이터가 없습니다.")
        return
    
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
                    "차량번호": None,
                }
            else:
                checks = {
                    "날짜": date,
                    "총시간": bool(record.get("total_service_time", "")),
                    "시작시간": bool(record.get("start_time", "")),
                    "종료시간": bool(end_time),
                    "이동서비스": bool(record.get("transport_service", "")),
                    "차량번호": bool(record.get("transport_vehicles", "")),
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
                    "향상프로그램": None,
                    "일상생활훈련": None,
                    "인지활동프로그램": None,
                    "인지기능향상": None,
                    "특이사항": None
                }
            else:
                recovery_checks = {
                    "날짜": date,
                    "향상프로그램": bool(record.get("prog_basic", "")),
                    "일상생활훈련": bool(record.get("prog_activity", "")),
                    "인지활동프로그램": bool(record.get("prog_cognitive", "")),
                    "인지기능향상": bool(record.get("prog_therapy", "")),
                    "특이사항": bool(record.get("functional_note", ""))
                }
            
            results.append({
                CategoryType.BASIC_INFO.value: checks,
                CategoryType.PHYSICAL_ACTIVITY.value: physical_checks,
                CategoryType.COGNITIVE_CARE.value: cognitive_checks,
                CategoryType.NURSING_CARE.value: health_checks,
                CategoryType.FUNCTIONAL_RECOVERY.value: recovery_checks
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
        st.write("#### 카테고리별 정보")
        categories_korean = CategoryDisplay.KOREAN_NAMES
        categories = CategoryDisplay.KOREAN_NAMES

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
                    
                    if category == CategoryType.BASIC_INFO.value:
                        writers = [original_record.get(field) for field in WriterFields.WRITER_MAPPING[category]]
                        row["작성자"] = next((w for w in writers if w), "")
                    else:
                        writer_field = WriterFields.WRITER_MAPPING[category][0]
                        row["작성자"] = original_record.get(writer_field) or ""

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

    # 직원 평가 폼 (카테고리별 정보 테이블 하단)
    _render_employee_evaluation_form(person_records, person_name)

    # 선택적 필드 섹션 (상시 표시)
    st.divider()
    st.write("### 추가 정보")
    
    # 모든 선택적 필드를 하나로 합치기
    all_optional_fields = {
        **OptionalFields.PHYSICAL_ACTIVITY_OPTIONAL,
        **OptionalFields.NURSING_CARE_OPTIONAL,
        **OptionalFields.FUNCTIONAL_RECOVERY_OPTIONAL
    }
    
    # 테이블 데이터 생성
    table_data = []
    non_default_count = 0
    total_count = 0
    
    for record in person_records:
        row = {"날짜": record.get("date", "")}
        
        # 각 선택적 필드 값 추가
        for display_name, field_name in all_optional_fields.items():
            value = record.get(field_name, "-")
            # 특수 처리가 필요한 필드들
            if field_name == "bath_time" and value != "-" and record.get("bath_method", "-") != "-":
                value = f"{value} / {record.get('bath_method', '-')}"
            elif field_name == "bath_method" and field_name == "bath_method":
                continue  # bath_time에서 이미 처리했으므로 건너뛰기
            
            row[display_name] = value
            
            # 기본값이 아닌 경우 카운트 (0, 없음 / , -, 미실시 등은 제외)
            if value not in ['0', '-', '미실시', '없음', '', None, '없음 / ']:
                non_default_count += 1
            total_count += 1
        
        table_data.append(row)
    
    # 상단에 요약 정보 표시
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown(f"<p style='text-align: center; color: gray; margin-bottom: 5px;'>추가 정보 작성 현황</p>", unsafe_allow_html=True)
        # 1건 이상일 때만 주황색, 아니면 검은색
        color = 'orange' if non_default_count > 0 else 'black'
        st.markdown(f"<h3 style='text-align: center; color: {color}; margin: 0px;'>{non_default_count}건</h3>", unsafe_allow_html=True)
    
    if table_data:
        df = pd.DataFrame(table_data)
        
        # 기본값이 아닌 셀에 강조 표시 (1건 이상일 때만)
        def highlight_non_default(val):
            # 기본값 목록
            default_values = ['0', '-', '미실시', '없음', '', None, '없음 / ']
            if val in default_values or non_default_count == 0:
                return ''
            return 'background-color: #ffeb3b; color: #000'  # 노란색 배경
        
        # 날짜 열은 제외하고 스타일 적용
        styled_df = df.style.applymap(
            highlight_non_default,
            subset=[col for col in df.columns if col != '날짜']
        )
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # 고객 정보는 별도로 표시
        st.markdown("---")
        st.write("**👤 고객 정보**")
        if person_records:
            first_record = person_records[0]
            customer_info_data = []
            for display_name, field_name in OptionalFields.CUSTOMER_INFO.items():
                value = first_record.get(field_name, "-")
                customer_info_data.append({"항목": display_name, "값": value})
            
            df_customer = pd.DataFrame(customer_info_data)
            st.dataframe(df_customer, use_container_width=True, hide_index=True)

    st.divider()
    st.write("### 📝 특이사항 AI 평가 실행")
    st.info("모든 날짜의 특이사항을 일괄 평가하여 수정 제안을 받습니다.")
    
    if st.button("🚀 전체 특이사항 평가 시작", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(person_records)
        
        # 평가 결과 저장용 딕셔너리
        eval_results = []
        
        for i, record in enumerate(person_records):
            date = record.get("date", "날짜 없음")
            status_text.text(f"🔍 {date} 특이사항 평가 중... ({i+1}/{total})")
            
            physical_note = record.get("physical_note", "")
            cognitive_note = record.get("cognitive_note", "")
            
            if physical_note.strip() or cognitive_note.strip():
                with st.spinner(f"{date} 특이사항 평가 중..."):
                    # 날짜별 독립 처리 - 누적 데이터 초기화
                    result = evaluation_service.evaluate_special_note_with_ai(record)
                    
                    if result:
                        # record_id 조회
                        customer_name = record.get('customer_name', '')
                        print(f"DEBUG: record_id 조회 - customer_name={customer_name}, date={date}")
                        
                        record_id = evaluation_service.get_record_id(
                            customer_name,
                            date
                        )
                        
                        print(f"DEBUG: 조회된 record_id={record_id}")
                        
                        if record_id:
                            # DB에 평가 결과 저장 (원본 특이사항 텍스트 추가)
                            result_with_notes = result.copy()
                            result_with_notes['physical_note'] = physical_note
                            result_with_notes['cognitive_note'] = cognitive_note
                            
                            evaluation_service.save_special_note_evaluation(
                                record_id, result_with_notes
                            )
                            print(f"DEBUG: DB 저장 완료 - record_id={record_id}")
                        else:
                            print(f"DEBUG: DB 저장 실패 - record_id를 찾을 수 없음")
                        
                        # 평가 결과 저장
                        eval_result = {
                            "date": date,
                            "physical_note": physical_note,
                            "cognitive_note": cognitive_note,
                            "physical_result": result.get("physical", {}),
                            "cognitive_result": result.get("cognitive", {}),
                            "original_physical": result.get("original_physical", {}),
                            "original_cognitive": result.get("original_cognitive", {})
                        }
                        eval_results.append(eval_result)
            
            progress_bar.progress((i + 1) / total)
        
        st.success("✅ 전체 특이사항 평가가 완료되었습니다!")
        
        # 평가 결과를 세션 상태에 저장
        st.session_state.special_note_eval_results = eval_results

    # 특이사항 평가 결과 테이블
    st.divider()
    st.write("### 📊 특이사항 평가 결과")
    
    # 신체활동 특이사항 평가 결과
    st.write("#### 🏃 신체활동 특이사항")
    physical_evaluations = []
    
    # 현재 사람의 모든 기록에 대해 평가 결과 확인
    for record in person_records:
        date = record.get("date", "")
        physical_note = record.get("physical_note", "")
        total_service_time = record.get("total_service_time", "").strip()
        
        # record_id 조회 - person_name 사용 (record의 customer_name이 비어있을 수 있음)
        customer_name_for_query = record.get('customer_name') or person_name
        record_id = evaluation_service.get_record_id(
            customer_name_for_query,
            date
        )
        
        # 총시간이 미이용/일정없음/결석인 경우
        if total_service_time in ["미이용", "일정없음", "결석"]:
            physical_evaluations.append({
                "날짜": date,
                "원본 등급": "평가없음",
                "수정 제안": "미이용",
                "원본 내용": physical_note
            })
        elif physical_note.strip():
            # DB에서 수정 제안과 등급 조회
            evaluation = {
                'suggestion': '',
                'grade': '평가없음'
            }
            
            if record_id:
                evaluation = evaluation_service.get_evaluation_from_db(
                    record_id, 'SPECIAL_NOTE_PHYSICAL'
                )
            
            physical_evaluations.append({
                "날짜": date,
                "원본 등급": evaluation['grade'],
                "수정 제안": evaluation['suggestion'],
                "원본 내용": physical_note
            })
    
    if physical_evaluations:
        df_physical = pd.DataFrame(physical_evaluations)
        
        # "개선" 등급의 행을 초록색으로 표시
        def highlight_improvement_physical(row):
            return ['color: green' if row['원본 등급'] == '개선' else '' for _ in row]
        
        styled_df = df_physical.style.apply(highlight_improvement_physical, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("신체활동 특이사항이 없거나 평가되지 않았습니다.")
    
    # 인지관리 특이사항 평가 결과
    st.write("#### 🧠 인지관리 특이사항")
    cognitive_evaluations = []
    
    # 현재 사람의 모든 기록에 대해 평가 결과 확인
    for record in person_records:
        date = record.get("date", "")
        cognitive_note = record.get("cognitive_note", "")
        total_service_time = record.get("total_service_time", "").strip()
        
        # record_id 조회 - person_name 사용 (record의 customer_name이 비어있을 수 있음)
        customer_name_for_query = record.get('customer_name') or person_name
        record_id = evaluation_service.get_record_id(
            customer_name_for_query,
            date
        )
        
        # 총시간이 미이용/일정없음/결석인 경우
        if total_service_time in ["미이용", "일정없음", "결석"]:
            cognitive_evaluations.append({
                "날짜": date,
                "원본 등급": "평가없음",
                "수정 제안": "미이용",
                "원본 내용": cognitive_note
            })
        elif cognitive_note.strip():
            # DB에서 수정 제안과 등급 조회
            evaluation = {
                'suggestion': '',
                'grade': '평가없음'
            }
            
            if record_id:
                evaluation = evaluation_service.get_evaluation_from_db(
                    record_id, 'SPECIAL_NOTE_COGNITIVE'
                )
            
            cognitive_evaluations.append({
                "날짜": date,
                "원본 등급": evaluation['grade'],
                "수정 제안": evaluation['suggestion'],
                "원본 내용": cognitive_note
            })
    
    if cognitive_evaluations:
        df_cognitive = pd.DataFrame(cognitive_evaluations)
        
        # "개선" 등급의 행을 초록색으로 표시
        def highlight_improvement_cognitive(row):
            return ['color: green' if row['원본 등급'] == '개선' else '' for _ in row]
        
        styled_df = df_cognitive.style.apply(highlight_improvement_cognitive, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("인지관리 특이사항이 없거나 평가되지 않았습니다.")


def _render_employee_evaluation_form(person_records: list, person_name: str):
    """직원 평가 폼 렌더링 (카테고리별 정보 테이블 하단)"""
    if not person_records:
        return
    
    emp_eval_repo = EmployeeEvaluationRepository()
    
    # 세션 상태 초기화
    if 'last_emp_eval_id' not in st.session_state:
        st.session_state.last_emp_eval_id = None
    if 'emp_eval_save_time' not in st.session_state:
        st.session_state.emp_eval_save_time = None
    
    # PDF에서 파싱된 직원 이름 수집 (중복 제거)
    writer_names = set()
    for record in person_records:
        for field in ['writer_phy', 'writer_nur', 'writer_cog', 'writer_func']:
            writer = record.get(field)
            if writer and writer.strip():
                writer_names.add(writer.strip())
    
    writer_list = sorted(list(writer_names)) if writer_names else []
    
    if not writer_list:
        return
    
    # 카테고리 및 평가 유형 옵션
    category_options = ['공통', '신체', '인지', '간호', '기능']
    evaluation_type_options = ['누락', '내용부족', '오타', '문법']
    
    with st.form(key="employee_evaluation_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            selected_target = st.selectbox(
                "평가 대상",
                options=writer_list,
                index=0
            )
            selected_category = st.selectbox(
                "카테고리",
                options=category_options,
                index=1  # 기본값 "신체"
            )
        
        with col2:
            selected_eval_type = st.selectbox(
                "평가 유형",
                options=evaluation_type_options,
                index=0  # 기본값 "누락"
            )
            comment = st.text_area(
                "코멘트 (선택사항)",
                placeholder="평가에 대한 추가 코멘트를 입력하세요...",
                height=68
            )
        
        submitted = st.form_submit_button("평가 저장", type="primary")
        
        if submitted:
            # 평가 대상 user_id 조회
            target_user_id = emp_eval_repo.get_user_id_by_name(selected_target)
            
            if not target_user_id:
                st.error(f"'{selected_target}' 직원을 DB에서 찾을 수 없습니다.")
                return
            
            # record_id 조회 (첫 번째 레코드 기준)
            first_record = person_records[0]
            customer_name = first_record.get('customer_name') or person_name
            record_date = first_record.get('date')
            
            record_id = evaluation_service.get_record_id(customer_name, record_date)
            
            if not record_id:
                st.error("해당 기록의 record_id를 찾을 수 없습니다.")
                return
            
            # 평가 저장
            try:
                emp_eval_id = emp_eval_repo.save_evaluation(
                    record_id=record_id,
                    target_user_id=target_user_id,
                    category=selected_category,
                    evaluation_type=selected_eval_type,
                    evaluation_date=date.today(),
                    evaluator_user_id=1,  # 추후 동적 변경
                    score=1,  # 기본값 1 고정
                    comment=comment if comment.strip() else None
                )
                # 세션에 저장된 ID와 시간 기록
                st.session_state.last_emp_eval_id = emp_eval_id
                st.session_state.emp_eval_save_time = time.time()
                st.toast("평가가 저장되었습니다.", icon="✅")
            except Exception as e:
                st.error(f"평가 저장 중 오류가 발생했습니다: {str(e)}")
    
    # 되돌리기 버튼 (10초 이내에만 표시)
    if st.session_state.last_emp_eval_id and st.session_state.emp_eval_save_time:
        elapsed = time.time() - st.session_state.emp_eval_save_time
        if elapsed < 10:
            remaining = int(10 - elapsed)
            if st.button(f"↩️ 되돌리기 ({remaining}초)", key="undo_emp_eval"):
                try:
                    emp_eval_repo.delete_evaluation(st.session_state.last_emp_eval_id)
                    st.session_state.last_emp_eval_id = None
                    st.session_state.emp_eval_save_time = None
                    st.toast("저장이 취소되었습니다.", icon="↩️")
                    st.rerun()
                except Exception as e:
                    st.error(f"되돌리기 중 오류가 발생했습니다: {str(e)}")
        else:
            # 10초 경과 시 세션 상태 초기화
            st.session_state.last_emp_eval_id = None
            st.session_state.emp_eval_save_time = None
