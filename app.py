import streamlit as st
import pandas as pd
import time
import hashlib

from modules.parser import CareRecordParser
from modules.parsing_database import save_parsed_data
from modules.ai_evaluator import AIEvaluator

# --- 페이지 설정 ---
st.set_page_config(page_title="요양기록 AI 매니저", layout="wide", page_icon="🏥")
st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("주간보호센터 기록 관리 시스템")

# --- 세션 상태 초기화 ---
if "docs" not in st.session_state:
    st.session_state.docs = []
if "active_doc_id" not in st.session_state:
    st.session_state.active_doc_id = None
if "ai_suggestion_tables" not in st.session_state:
    st.session_state.ai_suggestion_tables = {}
if "active_person_key" not in st.session_state:
    st.session_state.active_person_key = None
if "person_completion" not in st.session_state:
    st.session_state.person_completion = {}

# --- 헬퍼 함수 ---
def _get_active_doc():
    """현재 선택된 문서 객체를 반환합니다."""
    if not st.session_state.active_doc_id:
        return None
    for d in st.session_state.docs:
        if d.get("id") == st.session_state.active_doc_id:
            return d
    return None

def _get_person_keys_for_doc(doc):
    seen = set()
    keys = []
    for record in doc.get("parsed_data", []):
        person = record.get("customer_name") or "미상"
        key = f"{doc['id']}::{person}"
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys

def _iter_person_entries():
    entries = []
    for doc in st.session_state.docs:
        counts = {}
        for record in doc.get("parsed_data", []):
            person = record.get("customer_name") or "미상"
            key = f"{doc['id']}::{person}"
            if key not in counts:
                counts[key] = {
                    "key": key,
                    "doc_id": doc["id"],
                    "doc_name": doc["name"],
                    "person_name": person,
                    "record_count": 0,
                }
            counts[key]["record_count"] += 1
        entries.extend(counts.values())
    return entries

def _ensure_active_person():
    active_doc = _get_active_doc()
    if not active_doc:
        st.session_state.active_person_key = None
        return None

    key = st.session_state.get("active_person_key")
    if key and key.startswith(f"{active_doc['id']}::"):
        return key

    doc_keys = _get_person_keys_for_doc(active_doc)
    if doc_keys:
        st.session_state.active_person_key = doc_keys[0]
        return doc_keys[0]

    st.session_state.active_person_key = None
    return None

def _person_checkbox_key(person_key: str) -> str:
    return f"person_cb_{hashlib.sha1(person_key.encode('utf-8')).hexdigest()[:8]}"

def _select_person(person_key: str, doc_id: str):
    st.session_state.active_person_key = person_key
    st.session_state.active_doc_id = doc_id
    target = _person_checkbox_key(person_key)
    for key in list(st.session_state.keys()):
        if key.startswith("person_cb_"):
            st.session_state[key] = (key == target)

def _get_active_person_records():
    person_key = _ensure_active_person()
    if not person_key or "::" not in person_key:
        return None, None, []
    doc_id, person_name = person_key.split("::", 1)
    doc = next((d for d in st.session_state.docs if d["id"] == doc_id), None)
    if not doc:
        return None, None, []
    person_records = [
        r for r in doc.get("parsed_data", [])
        if (r.get("customer_name") or "미상") == person_name
    ]
    return doc, person_name, person_records

def _record_eval_key(record):
    person = record.get("customer_name") or "미상"
    date = record.get("date") or "-"
    return f"{person}::{date}"

def _get_person_done(key: str) -> bool:
    return st.session_state.person_completion.get(key, False)

def _set_person_done(key: str, value: bool):
    st.session_state.person_completion[key] = value

# --- 사이드바: 파일 업로드 및 선택 ---
with st.sidebar:
    nav = st.radio(
        "메뉴",
        options=["파일 처리", "수급자 관리"],
        index=0,
        horizontal=True,
        key="sidebar_nav_app",
    )
    if nav == "수급자 관리":
        st.switch_page("pages/customer_manage.py")

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
            st.session_state.active_person_key = None
            st.rerun()

    st.divider()

    if st.session_state.docs:
        if not st.session_state.active_doc_id:
            st.session_state.active_doc_id = st.session_state.docs[0]["id"]

        active_doc = _get_active_doc()
        st.subheader("📄 현재 파일")
        if active_doc:
            st.write(f"**{active_doc['name']}**")
        else:
            st.write("-")

        st.subheader("👥 파싱된 인원")
        person_entries = _iter_person_entries()
        if not person_entries:
            st.info("파싱된 인원이 없습니다.")
        else:
            st.caption("이름을 선택하면 메인 화면에 상세 기록이 표시됩니다.")
            active_person_key = _ensure_active_person()
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
                        use_container_width=True,
                        help=f"파일: {entry['doc_name']}"
                    ):
                        _select_person(entry["key"], entry["doc_id"])
                        st.rerun()
                with cols[1]:
                    done_value = st.checkbox(
                        "완료",
                        value=_get_person_done(entry["key"]),
                        key=f"done_{entry['key']}"
                    )
                    _set_person_done(entry["key"], done_value)
    else:
        st.info("좌측 상단에서 PDF 파일을 업로드해주세요.")

# --- 메인 화면 구성 ---
main_tab1, main_tab2 = st.tabs(["📄 기록 조회 및 DB 저장", "🤖 AI 품질 평가"])

# =========================================================
# [탭 1] 기록 상세 조회 및 DB 저장
# =========================================================
with main_tab1:
    doc_ctx, person_name, person_records = _get_active_person_records()
    active_doc = doc_ctx or _get_active_doc()

    if not active_doc:
        st.warning("👈 왼쪽 사이드바에서 파일을 선택하거나 업로드해주세요.")
    elif active_doc.get("error"):
        st.error(f"이 파일은 파싱 중 오류가 발생했습니다: {active_doc['error']}")
    elif not person_records:
        st.warning("선택된 어르신의 데이터가 없습니다.")
    else:
        data = person_records
        customer_name = person_name or (data[0].get('customer_name', '알 수 없음') if data else '알 수 없음')

        st.markdown(f"### 👤 대상자: **{customer_name}** 어르신")

        sub_tab_basic, sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "ℹ️ 기본 정보", "💪 신체활동지원", "🧠 인지관리", "🩺 간호관리", "🏃 기능회복"
        ])

        with sub_tab_basic:
            df_basic = pd.DataFrame([{
                "날짜": r.get('date'),
                "총시간": r.get('total_service_time', "-"),
                "시작시간": r.get('start_time') or "-",
                "종료시간": r.get('end_time') or "-",
                "이동서비스": r.get('transport_service', "미제공"),
                "차량번호": r.get('transport_vehicles', "")
            } for r in data])
            st.dataframe(df_basic, use_container_width=True, hide_index=True)

        with sub_tab1:
            df_phy = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('physical_note'),
                "세면/구강": r.get('hygiene_care'),
                "목욕": r.get('bath_time') if r.get('bath_time') == "없음" else f"{r.get('bath_time')} / {r.get('bath_method')}",
                "식사": f"{r.get('meal_breakfast')}/{r.get('meal_lunch')}/{r.get('meal_dinner')}",
                "화장실이용하기(기저기교환)": r.get('toilet_care'),
                "이동": r.get('mobility_care'),
                "작성자": r.get('writer_phy')
            } for r in data])
            st.dataframe(df_phy, use_container_width=True, hide_index=True)

        with sub_tab2:
            df_cog = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('cognitive_note'),
                "인지관리지원": r.get('cog_support'),
                "의사소통도움": r.get('comm_support'),
                "작성자": r.get('writer_cog')
            } for r in data])
            st.dataframe(df_cog, use_container_width=True, hide_index=True)

        with sub_tab3:
            df_nur = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('nursing_note'),
                "혈압/체온": r.get('bp_temp'),
                "건강관리(5분)": r.get('health_manage'),
                "간호관리": r.get('nursing_manage'),
                "응급서비스": r.get('emergency'),
                "작성자": r.get('writer_nur')
            } for r in data])
            st.dataframe(df_nur, use_container_width=True, hide_index=True)

        with sub_tab4:
            df_func = pd.DataFrame([{
                "날짜": r.get('date'),
                "특이사항": r.get('functional_note'),
                "향상 프로그램 내용": r.get('prog_enhance_detail'),
                "향상 프로그램 여부": r.get('prog_basic'),
                "인지활동 프로그램": r.get('prog_activity'),
                "인지기능 훈련": r.get('prog_cognitive'),
                "물리치료": r.get('prog_therapy'),
                "작성자": r.get('writer_func')
            } for r in data])
            st.dataframe(df_func, use_container_width=True, hide_index=True)

        st.divider()

        if st.button("💾 데이터베이스에 저장하기", type="primary", use_container_width=True):
            with st.spinner("DB 저장 중..."):
                count = save_parsed_data(data)
                if count > 0:
                    st.success(f"✅ {count}건의 기록이 안전하게 저장되었습니다!")
                    st.rerun()
                else:
                    st.error("저장에 실패했습니다. 로그를 확인해주세요.")

# =========================================================
# [탭 2] AI 품질 평가
# =========================================================
with main_tab2:
    doc_ctx, person_name, person_records = _get_active_person_records()
    active_doc = doc_ctx or _get_active_doc()

    if not active_doc:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 선택해주세요.")
    elif not person_records:
        st.warning("분석할 데이터가 없습니다.")
    else:
        st.markdown(f"### 📊 기록 품질 전수 조사 - {person_name or active_doc['name']}")

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
            total = len(person_records)

            for i, record in enumerate(person_records):
                status_text.text(f"🔍 {record.get('date')} 기록 분석 중...")
                result = evaluator.evaluate_daily_record(record)
                if result:
                    active_doc["eval_results"][record.get('date')] = result
                progress_bar.progress((i + 1) / total)
                time.sleep(0.05)

            status_text.text("✅ 분석 완료!")
            st.success("모든 평가가 완료되었습니다!")
            st.rerun()

        if active_doc.get("eval_results"):
            st.divider()
            st.write("### 📝 AI 분석 리포트")

            eval_tabs = st.tabs(["신체활동", "인지관리", "간호관리", "기능회복"])

            def show_eval_df(category_key, note_key, writer_key):
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
                for date, res in active_doc["eval_results"].items():
                    item = _pick_item(res or {}, category_key)
                    original_record = next((r for r in person_records if r["date"] == date), {})

                    grade = item.get("grade", "-")
                    if grade_filter != "전체" and grade != grade_filter:
                        continue

                    reason = item.get("reason", "")
                    if grade != "개선":
                        reason = ""

                    original_text = original_record.get(note_key, "")
                    if not original_text:
                        original_text = item.get("original_sentence", "")

                    rows.append({
                        "날짜": date,
                        "등급": grade,
                        "수정 제안": item.get("revised_sentence", ""),
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

            with eval_tabs[0]: show_eval_df("physical", "physical_note", "writer_phy")
            with eval_tabs[1]: show_eval_df("cognitive", "cognitive_note", "writer_cog")
            with eval_tabs[2]: show_eval_df("nursing", "nursing_note", "writer_nur")
            with eval_tabs[3]: show_eval_df("recovery", "functional_note", "writer_func")