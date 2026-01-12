"""사이드바 UI 모듈 - 파일 업로드 및 선택

성능 최적화:
- 파일 처리 후 즉시 메모리 해제
- 캐시 무효화로 메모리 관리
"""

import gc
import time
import streamlit as st
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from modules.pdf_parser import CareRecordParser
from modules.database import save_parsed_data
from modules.ui.ui_helpers import (
    get_active_doc, get_person_keys_for_doc, iter_person_entries, 
    ensure_active_person, person_checkbox_key, select_person,
    get_person_done, set_person_done, invalidate_person_cache
)


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        nav = st.radio(
            "메뉴",
            options=["파일 처리", "수급자 관리", "대시보드"],
            index=0,
            horizontal=True,
            key="sidebar_nav_app",
        )
        if nav == "수급자 관리":
            st.switch_page("pages/customer_manage.py")
        elif nav == "대시보드":
            st.switch_page("pages/dashboard.py")

        st.header("📂 파일 처리")

        # 1. 파일 업로드 섹션
        uploaded_files = st.file_uploader(
            "장기요양급여 제공기록지 PDF 업로드",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader"
        )

        if uploaded_files:
            newly_added_id = None
            for f in uploaded_files:
                file_bytes = f.getvalue()
                # 파일 내용 기반 해시 생성 (중복 방지)
                file_id_source = f"{f.name}\0".encode("utf-8") + file_bytes
                file_id = hashlib.sha256(file_id_source).hexdigest()[:16]

                # 이미 존재하는 파일인지 확인
                exists = any(d.get("id") == file_id for d in st.session_state.docs)

                if not exists:
                    try:
                        # 파싱 시작 시간 기록
                        start_time = time.time()
                        status_placeholder = st.empty()
                        
                        # 백그라운드에서 파싱 실행
                        from concurrent.futures import ThreadPoolExecutor, wait
                        import threading
                        
                        parser = CareRecordParser(f)
                        parsed = None
                        parsing_done = threading.Event()
                        
                        def do_parse():
                            nonlocal parsed
                            parsed = parser.parse()
                            parsing_done.set()
                        
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(do_parse)
                            
                            # 실시간 경과 시간 표시
                            while not parsing_done.is_set():
                                elapsed = time.time() - start_time
                                status_placeholder.info(f"📄 {f.name} 파싱 중... ({elapsed:.1f}초)")
                                time.sleep(0.5)
                            
                            future.result()  # 예외 발생 시 전파
                        
                        # 파싱 완료 시간 계산
                        elapsed_time = time.time() - start_time
                        total_records = len(parsed)
                        
                        # 완료 메시지 표시
                        status_placeholder.empty()
                        
                        # 파싱 후 파서 객체 해제
                        del parser
                        gc.collect()

                        new_doc = {
                            "id": file_id,
                            "name": f.name,
                            "completed": False,
                            "parsed_data": parsed,
                            "eval_results": {},
                            "error": None,
                        }
                        st.session_state.docs.append(new_doc)
                        newly_added_id = file_id # 새로 추가된 파일 ID 기记忆
                        
                        # 파싱 완료 메시지를 session_state에 저장
                        st.session_state.parsing_success = f"{total_records}건 데이터 조회 ({elapsed_time:.1f}초)"

                    except Exception as e:
                        st.error(f"{f.name} 처리 중 오류: {e}")
                        st.session_state.docs.append({
                            "id": file_id,
                            "name": f.name,
                            "completed": False,
                            "parsed_data": [],
                            "error": str(e),
                        })

            # 새로 추가된 파일이 있으면 그 파일로 자동 전환
            if newly_added_id:
                st.session_state.active_doc_id = newly_added_id
                st.session_state.active_person_key = None
                st.rerun()

        # 파싱 완료 메시지 표시
        if 'parsing_success' in st.session_state:
            st.success(st.session_state.parsing_success)
            del st.session_state.parsing_success

        st.divider()

        if st.session_state.docs:
            if not st.session_state.active_doc_id:
                st.session_state.active_doc_id = st.session_state.docs[0]["id"]

            active_doc = get_active_doc()
            st.subheader("📄 현재 파일")
            if active_doc:
                st.write(f"**{active_doc['name']}**")
            else:
                st.write("-")

            if active_doc and active_doc.get("parsed_data"):
                # Auto-save all parsed data to DB (only once)
                if not active_doc.get("db_saved"):
                    with st.spinner("DB 자동 저장 중..."):
                        count = save_parsed_data(active_doc["parsed_data"])
                        if count > 0:
                            st.toast(f"{count}건의 기록이 자동 저장되었습니다.", icon="✅")
                            # Mark as saved
                            for doc in st.session_state.docs:
                                if doc["id"] == active_doc["id"]:
                                    doc["db_saved"] = True
                                    break

            # Batch AI Processing buttons
            person_entries = iter_person_entries()
            if person_entries:
                st.divider()
                st.markdown("#### 전체인원 AI 처리")
                
                # Custom CSS for green text color
                st.markdown("""
                <style>
                .green-text {
                    color: #00C851 !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("주간 상태 변화 기록 생성",
                               use_container_width=True, 
                               help="전체 인원의 주간 상태변화 기록지를 일괄 생성합니다"):
                        _batch_generate_weekly_reports(person_entries)
                with col2:
                    if st.button("일일 특이사항 평가",
                               use_container_width=True,
                               help="전체 인원의 특이사항을 일괄 평가합니다"):
                        _batch_evaluate_all_optimized(person_entries)

            # 프래그먼트로 사람 목록 렌더링 (부분 리렌더링 최적화)
            _render_person_list_fragment()
        else:
            st.info("좌측 상단에서 PDF 파일을 업로드해주세요.")


@st.fragment
def _render_person_list_fragment():
    """사람 목록 렌더링 (프래그먼트로 부분 리렌더링 최적화)
    
    @st.fragment: 이 컴포넌트만 독립적으로 리렌더링되어 전체 페이지 새로고침 방지
    """
    person_entries = iter_person_entries()
    person_count = len(person_entries)
    st.subheader(f"👥 전체 {person_count}명")
    
    if not person_entries:
        st.info("파싱된 인원이 없습니다.")
        return
    
    st.caption("이름을 선택하면 상세 기록이 표시됩니다.")
    active_person_key = ensure_active_person()
    
    for entry in person_entries:
        is_active = entry["key"] == active_person_key
        cols = st.columns([0.75, 0.25])
        display_label = f"{entry['person_name']} · {entry['record_count']}건"
        button_type = "primary" if is_active else "secondary"
        
        with cols[0]:
            if st.button(
                display_label,
                key=f"person_btn_{entry['key']}",
                type=button_type,
                use_container_width=True
            ):
                select_person(entry["key"], entry["doc_id"])
                st.rerun()
        
        with cols[1]:
            done_value = st.checkbox(
                "완료",
                value=get_person_done(entry["key"]),
                key=f"done_{entry['key']}"
            )
            set_person_done(entry["key"], done_value)


def _batch_generate_weekly_reports(person_entries):
    """전체 인원의 주간 상태변화 기록지를 일괄 생성합니다."""
    if not person_entries:
        st.warning("처리할 인원이 없습니다.")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(person_entries)
    
    for i, entry in enumerate(person_entries):
        status_text.text(f"{entry['person_name']} 진행중 ({i+1}/{total})")
        
        # Get person records
        doc = next((d for d in st.session_state.docs if d["id"] == entry["doc_id"]), None)
        if not doc:
            continue
            
        person_records = [
            r for r in doc.get("parsed_data", [])
            if (r.get("customer_name") or "미상") == entry["person_name"]
        ]
        
        if not person_records:
            continue
            
        # Resolve customer_id
        from modules.customers import resolve_customer_id
        customer_id = (person_records[0].get("customer_id") if person_records else None)
        if customer_id is None:
            try:
                customer_id = resolve_customer_id(
                    name=entry["person_name"],
                    recognition_no=(person_records[0].get("customer_recognition_no") if person_records else None),
                    birth_date=(person_records[0].get("customer_birth_date") if person_records else None),
                )
            except Exception:
                customer_id = None
        
        if customer_id is None:
            continue
        
        # Compute weekly status
        from modules.weekly_data_analyzer import compute_weekly_status
        week_dates = sorted([r.get("date") for r in person_records if r.get("date")])
        if not week_dates:
            continue
            
        week_start = week_dates[-1]
        result = compute_weekly_status(entry["person_name"], week_start, customer_id)
        
        if result.get("error") or not result.get("scores"):
            continue
            
        # Generate AI report
        from modules.services.weekly_report_service import report_service
        from modules.database import save_weekly_status
        prev_range, curr_range = result["ranges"]
        ai_payload = result.get("trend", {}).get("ai_payload")
        
        if ai_payload:
            try:
                report = report_service.generate_weekly_report(
                    entry["person_name"],
                    (prev_range[0], curr_range[1]),
                    ai_payload,
                )
                
                if not isinstance(report, dict) or not report.get("error"):
                    text_report = report if isinstance(report, str) else str(report)
                    save_weekly_status(
                        customer_id=customer_id,
                        start_date=prev_range[0],
                        end_date=curr_range[1],
                        report_text=text_report,
                    )
            except Exception:
                pass
        
        progress_bar.progress((i + 1) / total)
    
    status_text.text("✅ 모든 인원의 주간 상태변화 기록지 생성이 완료되었습니다.")
    st.toast("✅ 일괄 처리 완료!", icon="✅")


def _batch_evaluate_all(person_entries):
    """전체 인원의 특이사항을 일괄 평가합니다."""
    if not person_entries:
        st.warning("처리할 인원이 없습니다.")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(person_entries)
    
    for i, entry in enumerate(person_entries):
        status_text.text(f"{entry['person_name']} 진행중 ({i+1}/{total})")
        
        # Get person records from database
        try:
            from modules.db_connection import db_query
            from modules.services.daily_report_service import evaluation_service
            
            with db_query() as cursor:
                # Get customer_id first
                cursor.execute(
                    "SELECT customer_id FROM customers WHERE name = %s LIMIT 1",
                    (entry["person_name"],)
                )
                customer_result = cursor.fetchone()
                
                if not customer_result:
                    continue
                    
                customer_id = customer_result["customer_id"]
                
                # Get records for this customer
                cursor.execute(
                    """
                    SELECT di.record_id, c.name as customer_name, di.date, 
                           dp.note as physical_note, dc.note as cognitive_note, 
                           dn.note as nursing_note, dr.note as functional_note,
                           dp.writer_name as writer_physical, dc.writer_name as writer_cognitive, 
                           dn.writer_name as writer_nursing, dr.writer_name as writer_recovery
                    FROM daily_infos di
                    LEFT JOIN customers c ON di.customer_id = c.customer_id
                    LEFT JOIN daily_physicals dp ON dp.record_id = di.record_id
                    LEFT JOIN daily_cognitives dc ON dc.record_id = di.record_id
                    LEFT JOIN daily_nursings dn ON dn.record_id = di.record_id
                    LEFT JOIN daily_recoveries dr ON dr.record_id = di.record_id
                    WHERE di.customer_id = %s
                    ORDER BY di.date DESC
                    """,
                    (customer_id,)
                )
                
                records = []
                for row in cursor.fetchall():
                    records.append({
                        "record_id": row["record_id"],
                        "customer_name": row["customer_name"],
                        "date": row["date"],
                        "physical_note": row["physical_note"],
                        "cognitive_note": row["cognitive_note"],
                        "nursing_note": row["nursing_note"],
                        "functional_note": row["functional_note"],
                        "writer_physical": row["writer_physical"],
                        "writer_cognitive": row["writer_cognitive"],
                        "writer_nursing": row["writer_nursing"],
                        "writer_recovery": row["writer_recovery"]
                    })
            
            # Evaluate all records for this person using process_daily_note_evaluation
            # 특이사항 평가는 PHYSICAL과 COGNITIVE만 수행
            for record in records:
                categories = [
                    ("PHYSICAL", record.get("physical_note", ""), record.get("writer_physical")),
                    ("COGNITIVE", record.get("cognitive_note", ""), record.get("writer_cognitive"))
                ]
                
                for category, text, category_writer in categories:
                    # 빈 텍스트는 건너뛰기
                    if not text or text.strip() in ['특이사항 없음', '결석', '']:
                        continue
                    
                    note_writer_id = record.get(f"writer_{category.lower()}_id", 1)
                    
                    evaluation_service.process_daily_note_evaluation(
                        record_id=record["record_id"],
                        category=category,
                        note_text=text,
                        note_writer_user_id=note_writer_id,
                        writer=category_writer or "",
                        customer_name=record.get("customer_name", ""),
                        date=record.get("date", "")
                    )
            
        except Exception as e:
            st.error(f"{entry['person_name']} 평가 중 오류: {e}")
        
        progress_bar.progress((i + 1) / total)
    
    status_text.text("✅ 모든 인원의 특이사항 평가가 완료되었습니다.")
    st.toast("✅ 일괄 평가 완료!", icon="✅")
    st.rerun()


def _batch_evaluate_all_optimized(person_entries):
    """성능 최적화된 전체 인원 특이사항 일괄 평가"""
    if not person_entries:
        st.warning("처리할 인원이 없습니다.")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(person_entries)
    
    # 모든 사람의 데이터를 한 번에 가져오기
    all_records = {}
    try:
        from modules.db_connection import db_query
        from modules.services.daily_report_service import evaluation_service
        
        with db_query() as cursor:
            # 모든 고객 ID 미리 조회
            customer_names = [entry["person_name"] for entry in person_entries]
            placeholders = ', '.join(['%s'] * len(customer_names))
            cursor.execute(
                f"SELECT customer_id, name FROM customers WHERE name IN ({placeholders})",
                customer_names
            )
            customer_map = {row["name"]: row["customer_id"] for row in cursor.fetchall()}
            
            # 모든 레코드 한 번에 조회
            if customer_map:
                customer_ids = list(customer_map.values())
                placeholders = ', '.join(['%s'] * len(customer_ids))
                cursor.execute(f"""
                    SELECT di.record_id, di.customer_id, c.name as customer_name, di.date, 
                           dp.note as physical_note, dc.note as cognitive_note, 
                           dn.note as nursing_note, dr.note as functional_note,
                           dp.writer_name as writer_physical, dc.writer_name as writer_cognitive, 
                           dn.writer_name as writer_nursing, dr.writer_name as writer_recovery
                    FROM daily_infos di
                    LEFT JOIN customers c ON di.customer_id = c.customer_id
                    LEFT JOIN daily_physicals dp ON dp.record_id = di.record_id
                    LEFT JOIN daily_cognitives dc ON dc.record_id = di.record_id
                    LEFT JOIN daily_nursings dn ON dn.record_id = di.record_id
                    LEFT JOIN daily_recoveries dr ON dr.record_id = di.record_id
                    WHERE di.customer_id IN ({placeholders})
                    ORDER BY di.customer_id, di.date DESC
                """, customer_ids)
                
                # 고객별로 그룹화
                for row in cursor.fetchall():
                    customer_id = row["customer_id"]
                    if customer_id not in all_records:
                        all_records[customer_id] = []
                    all_records[customer_id].append({
                        "record_id": row["record_id"],
                        "customer_name": row["customer_name"],
                        "date": row["date"],
                        "physical_note": row["physical_note"],
                        "cognitive_note": row["cognitive_note"],
                        "nursing_note": row["nursing_note"],
                        "functional_note": row["functional_note"],
                        "writer_physical": row["writer_physical"],
                        "writer_cognitive": row["writer_cognitive"],
                        "writer_nursing": row["writer_nursing"],
                        "writer_recovery": row["writer_recovery"]
                    })
    
    except Exception as e:
        st.error(f"데이터 조회 중 오류: {e}")
        return
    
    # 이미 평가된 항목 확인 (캐시 확인)
    evaluated_cache = set()
    try:
        with db_query() as cursor:
            if customer_map:
                customer_ids = list(customer_map.values())
                placeholders = ', '.join(['%s'] * len(customer_ids))
                cursor.execute(f"""
                    SELECT record_id, category FROM ai_evaluations 
                    WHERE record_id IN (
                        SELECT DISTINCT record_id FROM daily_infos 
                        WHERE customer_id IN ({placeholders})
                    )
                """, customer_ids)
                evaluated_cache = {(row["record_id"], row["category"]) for row in cursor.fetchall()}
    except:
        pass  # 캐시 실패 시 전체 평가 진행
    
    # 병렬 평가 처리
    def evaluate_record_batch(args):
        """레코드 배치 평가 함수"""
        records, person_name = args
        results = []
        
        # 카테고리 매핑 (영어 -> 한국어)
        category_to_korean = {
            "PHYSICAL": "신체",
            "COGNITIVE": "인지"
        }
        
        for record in records:
            # 특이사항 평가는 PHYSICAL과 COGNITIVE만 수행
            categories = [
                ("PHYSICAL", record.get("physical_note", ""), record.get("writer_physical")),
                ("COGNITIVE", record.get("cognitive_note", ""), record.get("writer_cognitive"))
            ]
            
            for category, text, category_writer in categories:
                # 캐시 확인 (한국어 카테고리로 확인)
                korean_category = category_to_korean.get(category, category)
                cache_key = (record["record_id"], korean_category)
                if cache_key in evaluated_cache:
                    continue
                
                # 빈 텍스트는 건너뛰기
                if not text or text.strip() in ['특이사항 없음', '결석', '']:
                    continue
                
                try:
                    note_writer_id = record.get(f"writer_{category.lower()}_id", 1)
                    evaluation_service.process_daily_note_evaluation(
                        record_id=record["record_id"],
                        category=category,
                        note_text=text,
                        note_writer_user_id=note_writer_id,
                        writer=category_writer or "",
                        customer_name=record.get("customer_name", ""),
                        date=record.get("date", "")
                    )
                    results.append((record["record_id"], korean_category))
                except Exception as e:
                    print(f"평가 오류 ({person_name}, {category}): {e}")
        
        return results
    
    # ThreadPoolExecutor로 병렬 처리 (메모리 모드에 따라 동적 조정)
    from modules.utils.memory_utils import get_thread_max_workers
    completed_count = 0
    with ThreadPoolExecutor(max_workers=get_thread_max_workers()) as executor:
        # 각 사람의 데이터를 별도 태스크로 제출
        futures = []
        for entry in person_entries:
            person_name = entry["person_name"]
            customer_id = customer_map.get(person_name)
            if customer_id and customer_id in all_records:
                future = executor.submit(evaluate_record_batch, (all_records[customer_id], person_name))
                futures.append((future, person_name))
        
        # 완료된 태스크 처리
        for idx, (future, person_name) in enumerate(futures):
            # 평가 시작 표시
            status_text.text(f"{person_name} 진행중 ({idx + 1}/{total})")
            
            try:
                future.result()
                completed_count += 1
                progress_bar.progress(completed_count / total)
            except Exception as e:
                st.error(f"❌ {person_name} 평가 중 오류: {e}")
                completed_count += 1
                progress_bar.progress(completed_count / total)
    
    status_text.text("✅ 모든 인원의 특이사항 평가가 완료되었습니다.")
    st.toast("✅ 일괄 평가 완료!", icon="✅")
    st.rerun()
