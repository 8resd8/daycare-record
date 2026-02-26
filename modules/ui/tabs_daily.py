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
import concurrent.futures


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
        
        with st.expander("📝 상세 추가 정보", expanded=False):
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # 고객 정보는 별도로 표시
        st.divider()

        with st.expander("👤 수급자 정보", expanded=False):
            if person_records:
                first_record = person_records[0]
                customer_info_data = []
                for display_name, field_name in OptionalFields.CUSTOMER_INFO.items():
                    value = first_record.get(field_name, "-")
                    customer_info_data.append({"항목": display_name, "값": str(value)})
                
                df_customer = pd.DataFrame(customer_info_data)
                if "값" in df_customer.columns:
                    df_customer["값"] = df_customer["값"].astype(str)
                st.dataframe(df_customer, use_container_width=True, hide_index=True)

    st.divider()

    st.write("### 📝 특이사항 AI 평가 실행")

    if st.button("🚀 현재 인원 특이사항 평가", type="primary"):
        # 현재 선택된 수급자의 기록만 수집
        all_records = []
        for r in person_records:
            if r.get("physical_note", "").strip() or r.get("cognitive_note", "").strip():
                # 이미 평가된 결과가 있는지 확인 (중복 요청 방지)
                customer_name = r.get('customer_name', '')
                date_str = r.get('date', '')
                record_id = evaluation_service.get_record_id(customer_name, date_str)
                
                # DB에서 이미 신체/인지 평가가 모두 있는지 확인
                if record_id:
                    phys_eval = evaluation_service.get_evaluation_from_db(record_id, 'SPECIAL_NOTE_PHYSICAL')
                    cogn_eval = evaluation_service.get_evaluation_from_db(record_id, 'SPECIAL_NOTE_COGNITIVE')
                    
                    # 이미 평가가 완료된 건은 제외
                    if phys_eval['grade'] != '평가없음' and cogn_eval['grade'] != '평가없음':
                        continue
                        
                all_records.append(r)
        
        if not all_records:
            st.success("모든 기록이 이미 평가되었거나 평가할 특이사항이 없습니다.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(all_records)
        
        # 병렬 처리를 위한 함수 정의
        def process_record(record):
            date_str = record.get("date", "날짜 없음")
            customer_name = record.get('customer_name', '')
            physical_note = record.get("physical_note", "").strip()
            cognitive_note = record.get("cognitive_note", "").strip()
            
            try:
                # 개별 호출 전 로그
                print(f"DEBUG: Processing {customer_name} ({date_str})")
                
                result = evaluation_service.evaluate_special_note_with_ai(record)
                if result:
                    record_id = evaluation_service.get_record_id(customer_name, date_str)
                    if record_id:
                        result_with_notes = result.copy()
                        result_with_notes['physical_note'] = physical_note
                        result_with_notes['cognitive_note'] = cognitive_note
                        evaluation_service.save_special_note_evaluation(record_id, result_with_notes)
                return True
            except Exception as e:
                print(f"Error processing {customer_name} ({date_str}): {str(e)}")
                return False

        max_workers = 4
        completed = 0
        
        # UI 업데이트용 컨테이너
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_record = {executor.submit(process_record, rec): rec for rec in all_records}
            for future in concurrent.futures.as_completed(future_to_record):
                try:
                    # 각 작업의 결과를 기다림 (타임아웃 설정 가능)
                    future.result(timeout=40) 
                except concurrent.futures.TimeoutError:
                    print("DEBUG: Task timed out")
                except Exception as e:
                    print(f"DEBUG: Task error: {e}")
                
                completed += 1
                progress_bar.progress(completed / total)
                status_text.text(f"⏳ 특이사항 평가 진행 중... ({completed}/{total})")
        
        st.success(f"총 {total}건의 특이사항 평가가 완료되었습니다.")
        time.sleep(1) # 결과 확인을 위한 잠시 대기
        st.rerun()

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
                "작성자": record.get("writer_phy", ""),
                "등급": "평가없음",
                "수정 제안": "미이용",
                "원본 특이사항": physical_note
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
                "작성자": record.get("writer_phy", ""),
                "등급": evaluation['grade'],
                "수정 제안": evaluation['suggestion'],
                "원본 특이사항": physical_note
            })
    
    if physical_evaluations:
        df_physical = pd.DataFrame(physical_evaluations)
        
        # "개선" 등급의 행을 초록색으로 표시
        def highlight_improvement_physical(row):
            return ['color: green' if row['등급'] == '개선' else '' for _ in row]
        
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
                "작성자": record.get("writer_cog", ""),
                "등급": "평가없음",
                "수정 제안": "미이용",
                "원본 특이사항": cognitive_note
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
                "작성자": record.get("writer_cog", ""),
                "등급": evaluation['grade'],
                "수정 제안": evaluation['suggestion'],
                "원본 특이사항": cognitive_note
            })
    
    if cognitive_evaluations:
        df_cognitive = pd.DataFrame(cognitive_evaluations)
        
        # "개선" 등급의 행을 초록색으로 표시
        def highlight_improvement_cognitive(row):
            return ['color: green' if row['등급'] == '개선' else '' for _ in row]
        
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
    if 'emp_eval_comment_key' not in st.session_state:
        st.session_state.emp_eval_comment_key = 0
    if 'selected_eval_row' not in st.session_state:
        st.session_state.selected_eval_row = None
    
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
    evaluation_type_options = ['누락', '내용부족', '오타', '문법', '오류']
    
    # record_id 미리 조회 (폼 외부에서 사용)
    first_record = person_records[0]
    customer_name = first_record.get('customer_name') or person_name
    record_date = first_record.get('date')
    record_id = evaluation_service.get_record_id(customer_name, record_date)
    
    st.subheader("✏️ 평가 입력")
    
    # 선택된 행이 있으면 해당 값으로 초기화
    if st.session_state.selected_eval_row:
        selected_row = st.session_state.selected_eval_row
        default_target_idx = writer_list.index(selected_row['target_user_name']) if selected_row['target_user_name'] in writer_list else 0
        default_category_idx = category_options.index(selected_row['category']) if selected_row['category'] in category_options else 1
        default_eval_type_idx = evaluation_type_options.index(selected_row['evaluation_type']) if selected_row['evaluation_type'] in evaluation_type_options else 0
        default_target_date = selected_row['target_date'] if selected_row['target_date'] else record_date
        default_comment = selected_row['comment']

    else:
        default_target_idx = 0
        default_category_idx = 1
        default_eval_type_idx = 0
        default_target_date = record_date
        default_comment = ""
    
    # 입력 필드 (폼 외부)
    col1, col2 = st.columns(2)
    
    with col1:
        selected_target = st.selectbox(
            "평가 대상",
            options=writer_list,
            index=default_target_idx,
            key="emp_eval_target"
        )
        
        # 해당 날짜 입력 (평가 대상과 평가 유형 사이)
        target_date_input = st.date_input(
            "해당 날짜",
            value=default_target_date if default_target_date else date.today(),
            key="emp_eval_target_date"
        )
        
        selected_category = st.selectbox(
            "카테고리",
            options=category_options,
            index=default_category_idx,
            key="emp_eval_category"
        )
    
    with col2:
        selected_eval_type = st.selectbox(
            "평가 유형",
            options=evaluation_type_options,
            index=default_eval_type_idx,
            key="emp_eval_type"
        )
        comment = st.text_area(
            "코멘트 (선택사항)",
            value=default_comment,
            placeholder="평가에 대한 추가 코멘트를 입력하세요...",
            height=100,
            key=f"emp_eval_comment_{st.session_state.emp_eval_comment_key}"
        )
    
    # 되돌리기 버튼 표시 여부 확인 (저장 후 계속 표시)
    show_undo = st.session_state.last_emp_eval_id is not None
    undo_clicked = False
    
    # 버튼 레이아웃: 평가 저장(좌) - 수정(중) - 되돌리기(우)
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    with btn_col1:
        save_clicked = st.button("평가 저장", type="primary", key="save_emp_eval")
    
    with btn_col2:
        update_clicked = st.button("수정", key="update_emp_eval")
    
    with btn_col3:
        if show_undo:
            undo_clicked = st.button("↩️ 되돌리기", key="undo_emp_eval")
    
    # 평가 저장 처리
    if save_clicked:
        target_user_id = emp_eval_repo.get_user_id_by_name(selected_target)
        
        if not target_user_id:
            st.error(f"'{selected_target}' 직원을 DB에서 찾을 수 없습니다.")
        elif not record_id:
            st.error("해당 기록의 record_id를 찾을 수 없습니다.")
        else:
            try:
                emp_eval_id = emp_eval_repo.save_evaluation(
                    record_id=record_id,
                    target_user_id=target_user_id,
                    category=selected_category,
                    evaluation_type=selected_eval_type,
                    evaluation_date=date.today(),
                    target_date=target_date_input,
                    evaluator_user_id=1,
                    score=1,
                    comment=comment if comment.strip() else None
                )
                st.session_state.last_emp_eval_id = emp_eval_id
                st.session_state.emp_eval_save_time = time.time()
                st.session_state.emp_eval_toast_msg = "saved"
                st.session_state.emp_eval_comment_key += 1
                st.session_state.selected_eval_row = None
                st.rerun()
            except Exception as e:
                st.error(f"평가 저장 중 오류가 발생했습니다: {str(e)}")
    
    # 수정 처리
    if update_clicked:
        target_user_id = emp_eval_repo.get_user_id_by_name(selected_target)
        
        if not target_user_id:
            st.error(f"'{selected_target}' 직원을 DB에서 찾을 수 없습니다.")
        elif not record_id:
            st.error("해당 기록의 record_id를 찾을 수 없습니다.")
        else:
            # 기존 평가 조회
            existing_id = emp_eval_repo.find_existing_evaluation(
                record_id, target_user_id, selected_category, selected_eval_type
            )
            
            if existing_id:
                try:
                    emp_eval_repo.update_evaluation(
                        emp_eval_id=existing_id,
                        evaluation_date=date.today(),
                        target_date=target_date_input,
                        evaluator_user_id=1,
                        score=1,
                        comment=comment if comment.strip() else None
                    )
                    st.session_state.emp_eval_toast_msg = "updated"
                    st.session_state.selected_eval_row = None
                    st.rerun()
                except Exception as e:
                    st.error(f"평가 수정 중 오류가 발생했습니다: {str(e)}")
            else:
                st.session_state.emp_eval_toast_msg = "no_update"
                st.rerun()
    
    # 되돌리기 처리
    if show_undo and undo_clicked:
        try:
            emp_eval_repo.delete_evaluation(st.session_state.last_emp_eval_id)
            st.session_state.last_emp_eval_id = None
            st.session_state.emp_eval_save_time = None
            st.session_state.emp_eval_toast_msg = "undone"
            st.rerun()
        except Exception as e:
            st.error(f"되돌리기 중 오류가 발생했습니다: {str(e)}")
    
    # Toast 메시지 표시 (rerun 후 표시)
    if st.session_state.get('emp_eval_toast_msg'):
        msg = st.session_state.emp_eval_toast_msg
        st.session_state.emp_eval_toast_msg = None
        if msg == "saved":
            st.toast("평가가 저장되었습니다.", icon="✅")
        elif msg == "updated":
            st.toast("평가가 수정되었습니다.", icon="✏️")
        elif msg == "undone":
            st.toast("저장이 취소되었습니다.", icon="↩️")
        elif msg == "no_update":
            st.toast("수정할 기존 평가가 없습니다.", icon="⚠️")
