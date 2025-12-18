import streamlit as st
import pandas as pd
import time
import hashlib

# 모듈 import (실제 환경에 modules 폴더가 있어야 함)
# 테스트 시 주석 처리하거나 더미 데이터를 사용하세요.
try:
    from modules.parser import CareRecordParser
    from modules.database import save_parsed_data
    from modules.ai_evaluator import AIEvaluator
except ImportError:
    # 로컬 테스트용 더미 클래스/함수 (모듈이 없을 경우를 대비한 안전장치)
    class CareRecordParser:
        def __init__(self, file): self.file = file
        def parse(self): return [{"date": "2024-01-01", "customer_name": "홍길동", "physical_note": "양호", "cognitive_note": "", "nursing_note": "", "functional_note": "", "bath_time": "없음", "meal_breakfast": "1", "meal_lunch": "1", "meal_dinner": "1", "toilet_care": "0", "mobility_care": "0", "writer_phy": "김복지", "cog_support": "", "comm_support": "", "writer_cog": "", "bp_temp": "", "health_manage": "", "nursing_manage": "", "emergency": "", "writer_nur": "", "prog_basic": "", "prog_activity": "", "prog_cognitive": "", "prog_therapy": "", "writer_func": ""}]

    def save_parsed_data(data): return len(data)

    class AIEvaluator:
        def evaluate_daily_record(self, record): return {"physical": {"grade": "A", "reason": "Good"}}

# --- 페이지 설정 ---
st.set_page_config(page_title="요양기록 AI 매니저", layout="wide", page_icon="🏥")
st.title("🏥 주간보호센터 기록 관리 시스템")

# --- 세션 상태 초기화 ---
if "docs" not in st.session_state:
    st.session_state.docs = []
if "active_doc_id" not in st.session_state:
    st.session_state.active_doc_id = None
if "ai_suggestion_tables" not in st.session_state:
    st.session_state.ai_suggestion_tables = {}

# --- 헬퍼 함수 ---
def _get_active_doc():
    """현재 선택된 문서 객체를 반환합니다."""
    if not st.session_state.active_doc_id:
        return None
    for d in st.session_state.docs:
        if d.get("id") == st.session_state.active_doc_id:
            return d
    return None

def _doc_display_name(doc):
    """문서 이름을 포맷팅합니다 (완료 여부 포함)."""
    name = doc.get("name", "(unknown)")
    if doc.get("completed"):
        return f"[완료] {name}"
    return name

# --- 사이드바: 파일 업로드 및 선택 ---
with st.sidebar:
    st.header("📂 파일 처리")

    # 1. 파일 업로드 섹션
    uploaded_files = st.file_uploader(
        "PDF 기록지 업로드",
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
                    with st.spinner(f"PDF 정밀 분석 중... ({f.name})"):
                        parser = CareRecordParser(f)
                        parsed = parser.parse()

                    new_doc = {
                        "id": file_id,
                        "name": f.name,
                        "completed": False,
                        "parsed_data": parsed,
                        "eval_results": {},
                        "error": None,
                    }
                    st.session_state.docs.append(new_doc)
                    newly_added_id = file_id # 새로 추가된 파일 ID 기억

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
            st.rerun()

    st.divider()

    # 2. 문서 선택 및 관리 섹션
    if st.session_state.docs:
        st.subheader("📋 문서 목록")

        # (1) 문서 선택 (Selectbox) - 여기가 핵심입니다.
        # ID와 이름을 매핑
        doc_map = {d["id"]: d for d in st.session_state.docs}
        doc_ids = [d["id"] for d in st.session_state.docs]

        # 현재 active_doc_id가 유효한지 확인
        if st.session_state.active_doc_id not in doc_ids:
            st.session_state.active_doc_id = doc_ids[0]

        selected_id = st.selectbox(
            "분석할 파일을 선택하세요:",
            options=doc_ids,
            format_func=lambda x: _doc_display_name(doc_map[x]),
            index=doc_ids.index(st.session_state.active_doc_id),
            key="sb_doc_selector" # 키를 지정하여 UI 안정성 확보
        )

        # 사용자가 선택을 변경했다면 세션 업데이트
        if selected_id != st.session_state.active_doc_id:
            st.session_state.active_doc_id = selected_id
            st.rerun()

        st.info(f"현재 선택됨: **{doc_map[st.session_state.active_doc_id]['name']}**")

        st.divider()

        # (2) 완료 여부 체크박스 (부가 기능)
        with st.expander("✅ 진행 상태 관리", expanded=True):
            for d in st.session_state.docs:
                is_active = (d["id"] == st.session_state.active_doc_id)
                label = d["name"]
                if is_active:
                    label = f"👉 {label}" # 현재 선택된 파일 강조

                checked = st.checkbox(
                    label,
                    value=d["completed"],
                    key=f"check_{d['id']}"
                )
                d["completed"] = checked

        # 초기화 버튼
        # if st.button("🗑️ 목록 전체 초기화", use_container_width=True):
        #     st.session_state.docs = []
        #     st.session_state.active_doc_id = None
        #     st.session_state.ai_suggestion_tables = {}
        #     st.rerun()

    else:
        st.info("좌측 상단에서 PDF 파일을 업로드해주세요.")

# --- 메인 화면 구성 ---
main_tab1, main_tab2 = st.tabs(["📄 기록 조회 및 DB 저장", "🤖 AI 품질 평가"])

# =========================================================
# [탭 1] 기록 상세 조회 및 DB 저장
# =========================================================
with main_tab1:
    active_doc = _get_active_doc()

    if not active_doc:
        st.warning("👈 왼쪽 사이드바에서 파일을 선택하거나 업로드해주세요.")
    elif active_doc.get("error"):
        st.error(f"이 파일은 파싱 중 오류가 발생했습니다: {active_doc['error']}")
    elif not active_doc.get("parsed_data"):
        st.warning("데이터가 없는 파일입니다.")
    else:
        data = active_doc["parsed_data"]
        # 안전한 접근을 위해 get 사용
        first_row = data[0] if data else {}
        customer_name = first_row.get('customer_name', '알 수 없음')

        st.markdown(f"### 👤 대상자: **{customer_name}** 어르신")

        # 4가지 상세 탭
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "💪 신체활동지원", "🧠 인지관리", "🩺 간호관리", "🏃 기능회복"
        ])

        # 데이터 프레임 생성 로직 (키 에러 방지를 위해 .get 사용 권장)
        def safe_get(record, key, default=""):
            return record.get(key, default) or ""

        # 1. 신체활동 탭
        with sub_tab1:
            df_phy = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('physical_note'),
                "세면/구강": r.get('hygiene_care'),
                "목욕": r.get('bath_time') if r.get('bath_time') == "없음" else f"{r.get('bath_time')} / {r.get('bath_method')}",
                "식사": f"{r.get('meal_breakfast')}/{r.get('meal_lunch')}/{r.get('meal_dinner')}",
                "이동": r.get('mobility_care'),
                "작성자": r.get('writer_phy')
            } for r in data])
            st.dataframe(df_phy, use_container_width=True, hide_index=True)

        # 2. 인지관리 탭
        with sub_tab2:
            df_cog = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('cognitive_note'),
                "인지관리지원": r.get('cog_support'),
                "의사소통도움": r.get('comm_support'),
                "작성자": r.get('writer_cog')
            } for r in data])
            st.dataframe(df_cog, use_container_width=True, hide_index=True)

        # 3. 간호관리 탭
        with sub_tab3:
            df_nur = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('nursing_note'),
                "혈압/체온": r.get('bp_temp'),
                "간호관리": r.get('nursing_manage'),
                "응급서비스": r.get('emergency'),
                "작성자": r.get('writer_nur')
            } for r in data])
            st.dataframe(df_nur, use_container_width=True, hide_index=True)

        # 4. 기능회복 탭
        with sub_tab4:
            df_func = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('functional_note'),
                "기본동작": r.get('prog_basic'),
                "치료내용": r.get('prog_therapy'),
                "작성자": r.get('writer_func')
            } for r in data])
            st.dataframe(df_func, use_container_width=True, hide_index=True)

        st.divider()

        # DB 저장 버튼
        if st.button("💾 데이터베이스에 저장하기", type="primary", use_container_width=True):
            with st.spinner("DB 저장 중..."):
                count = save_parsed_data(data)
                if count > 0:
                    st.success(f"✅ {count}건의 기록이 안전하게 저장되었습니다!")
                    # 저장 후 해당 문서를 완료 처리할 수도 있음
                    active_doc['completed'] = True
                    st.rerun()
                else:
                    st.error("저장에 실패했습니다. 로그를 확인해주세요.")

# =========================================================
# [탭 2] AI 품질 평가
# =========================================================
with main_tab2:
    active_doc = _get_active_doc()

    if not active_doc:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 선택해주세요.")
    elif not active_doc.get("parsed_data"):
        st.warning("분석할 데이터가 없습니다.")
    else:
        st.markdown(f"### 📊 기록 품질 전수 조사 - {active_doc['name']}")

        grade_filter = st.selectbox(
            "등급 필터",
            options=["개선", "우수", "평균", "전체"],
            index=0,
            key="ai_grade_filter",
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            start_btn = st.button("🚀 전체 평가 시작", type="primary")

        if start_btn:
            evaluator = AIEvaluator()
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(active_doc["parsed_data"])

            for i, record in enumerate(active_doc["parsed_data"]):
                status_text.text(f"🔍 {record.get('date')} 기록 분석 중...")

                # AI 평가 실행
                result = evaluator.evaluate_daily_record(record)
                if result:
                    active_doc["eval_results"][record.get('date')] = result

                progress_bar.progress((i + 1) / total)
                time.sleep(0.05)

            status_text.text("✅ 분석 완료!")
            st.success("모든 평가가 완료되었습니다!")
            st.rerun()

        # --- 평가 결과 표시 ---
        if active_doc.get("eval_results"):
            st.divider()
            st.write("### 📝 AI 분석 리포트")

            # 탭으로 구분하여 보여주기
            eval_tabs = st.tabs(["신체활동", "인지관리", "간호관리", "기능회복"])

            # 결과 표시를 위한 공통 함수
            def show_eval_df(category_key, note_key, writer_key):
                rows = []
                for date, res in active_doc["eval_results"].items():
                    item = (res or {}).get(category_key, {})
                    # 원본 기록 찾기
                    original_record = next((r for r in active_doc["parsed_data"] if r["date"] == date), {})

                    grade = item.get("grade", "-")
                    if grade_filter != "전체" and grade != grade_filter:
                        continue

                    reason = item.get("reason", "")
                    if grade != "개선":
                        reason = ""

                    rows.append({
                        "날짜": date,
                        "등급": grade,
                        "수정 제안": item.get("revised_sentence", ""),
                        "이유": reason,
                        "원본 내용": original_record.get(note_key, ""),
                        "작성자": original_record.get(writer_key, "")
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            with eval_tabs[0]: show_eval_df("physical", "physical_note", "writer_phy")
            with eval_tabs[1]: show_eval_df("cognitive", "cognitive_note", "writer_cog")
            with eval_tabs[2]: show_eval_df("nursing", "nursing_note", "writer_nur")
            with eval_tabs[3]: show_eval_df("recovery", "functional_note", "writer_func")