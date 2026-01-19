"""Microsoft Clarity 분석 도구 모듈"""

import os
import streamlit as st
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def inject_clarity_tracking():
    # .env 파일에서 Clarity 프로젝트 ID 읽기
    clarity_project_id = os.getenv('CLARITY_PROJECT_ID', '')
    
    if clarity_project_id:
        clarity_script = f"""
<script type="text/javascript">
    (function(c,l,a,r,i,t,y){{
        c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    }})(window, document, "clarity", "script", "{clarity_project_id}");
</script>
"""
        st.markdown(clarity_script, unsafe_allow_html=True)
        st.session_state.clarity_enabled = True
    else:
        # 개발 환경에서는 주석 처리된 코드 표시
        development_script = """
<!-- Microsoft Clarity 추적 코드 -->
<!-- 프로젝트 ID가 설정되면 활성화됩니다 -->
<!-- .env 파일에 CLARITY_PROJECT_ID=your_project_id 를 추가하세요 -->
"""
        st.markdown(development_script, unsafe_allow_html=True)
        st.session_state.clarity_enabled = False

def get_clarity_status():
    """Clarity 추적 상태를 반환합니다."""
    return st.session_state.get('clarity_enabled', False)

def setup_clarity_info():
    """Clarity 설정 정보를 표시합니다."""
    if get_clarity_status():
        st.success("Microsoft Clarity 활성화")
    else:
        st.info("ℹ️ Microsoft Clarity를 설정하려면:")
        st.code("""
1. https://clarity.microsoft.com/ 에서 프로젝트 생성
2. 프로젝트 ID 복사
3. .env 파일에 추가: CLARITY_PROJECT_ID=your_project_id
4. 앱 재시작
        """)
