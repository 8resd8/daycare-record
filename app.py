"""메인 애플리케이션 - UI 모듈 조립"""

import streamlit as st

# --- 페이지 설정 ---
st.set_page_config(page_title="요양기록 AI 매니저", layout="wide", page_icon="🏥")
st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"] { display: none; }
      section[data-testid="stSidebar"] div[id^="person_btn_"] button {
        background: transparent !important;
        border: none !important;
        color: inherit !important;
        text-align: left;
        padding-left: 0 !important;
      }
      section[data-testid="stSidebar"] div[id^="person_btn_"] button[kind="primary"] {
        color: #1f6feb !important;
        font-weight: 600;
      }
      section[data-testid="stSidebar"] div[id^="person_btn_"] button[kind="secondary"]:hover {
        color: #1f6feb !important;
      }
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

# --- UI 모듈 임포트 ---
from modules.ui import render_sidebar, render_records_tab, render_ai_evaluation_tab

# --- 사이드바 렌더링 ---
render_sidebar()

# --- 메인 화면 구성 ---
main_tab1, main_tab2 = st.tabs(["📄주간 상태 변화 평가", "데일리 특이사항 평가"])

# 탭 1: 기록 조회
with main_tab1:
    render_records_tab()

# 탭 2: AI 품질 평가
with main_tab2:
    render_ai_evaluation_tab()
