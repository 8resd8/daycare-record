"""메인 애플리케이션 - UI 모듈 조립
"""

import gc
import streamlit as st

if 'gc_optimized' not in st.session_state:
    gc.set_threshold(700, 10, 10)
    st.session_state.gc_optimized = True

# --- 페이지 설정 ---
st.set_page_config(page_title="요양기록 AI 매니저", layout="wide", page_icon="🏥")

# 세션 타임아웃 방지: 5분마다 자동 새로고침
st.markdown("""
<script>
(function() {
    // 5분(300초)마다 페이지 새로고침하여 세션 유지
    setInterval(function() {
        // 세션 유지를 위한 더미 요청
        fetch(window.location.href, { method: 'HEAD' });
    }, 300000); // 5분
    
    // 사용자 활동 감지
    let lastActivity = Date.now();
    ['mousedown', 'keydown', 'scroll', 'touchstart'].forEach(function(event) {
        document.addEventListener(event, function() {
            lastActivity = Date.now();
        });
    });
    
    // 30분 동안 활동이 없으면 경고 표시
    setInterval(function() {
        const inactiveTime = (Date.now() - lastActivity) / 1000 / 60;
        if (inactiveTime > 25 && inactiveTime < 30) {
            console.log('세션이 곧 만료됩니다. 활동을 감지하면 자동으로 유지됩니다.');
        }
    }, 60000); // 1분마다 체크
})();
</script>
""", unsafe_allow_html=True)

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
if "last_activity_time" not in st.session_state:
    import time
    st.session_state.last_activity_time = time.time()

# --- UI 모듈 임포트 ---
from modules.ui import render_sidebar, render_records_tab, render_ai_evaluation_tab

# --- 사이드바 렌더링 ---
render_sidebar()

# --- 메인 화면 구성 ---
main_tab1, main_tab2 = st.tabs(["📄주간 상태 변화 평가", "일일 특이사항 평가"])

# 탭 1: 기록 조회
with main_tab1:
    render_records_tab()

# 탭 2: AI 품질 평가
with main_tab2:
    render_ai_evaluation_tab()
