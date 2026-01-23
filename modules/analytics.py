"""Microsoft Clarity 분석 도구 모듈"""

import os
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def inject_clarity_tracking():
    # .env 파일에서 Clarity 프로젝트 ID 읽기
    clarity_project_id = os.getenv('CLARITY_PROJECT_ID', '')
    
    if clarity_project_id:
        # Clarity 스크립트를 부모 document의 head에 직접 삽입
        clarity_html = f"""
<!DOCTYPE html>
<html>
<head>
    <script type="text/javascript">
        (function() {{
            try {{
                var parentDoc = window.parent.document;
                var clarityId = "{clarity_project_id}";
                
                // 이미 Clarity 스크립트가 있는지 확인
                if (parentDoc.querySelector('script[src*="clarity.ms"]')) {{
                    return;
                }}
                
                // Clarity 초기화 함수 설정
                window.parent.clarity = window.parent.clarity || function() {{
                    (window.parent.clarity.q = window.parent.clarity.q || []).push(arguments);
                }};
                
                // Clarity 스크립트 태그 생성
                var script = parentDoc.createElement('script');
                script.async = true;
                script.src = "https://www.clarity.ms/tag/" + clarityId;
                
                // head에 스크립트 삽입
                var head = parentDoc.getElementsByTagName('head')[0];
                if (head) {{
                    head.appendChild(script);
                }}
            }} catch(e) {{
                console.log('Clarity injection error:', e);
            }}
        }})();
    </script>
</head>
<body></body>
</html>
"""
        components.html(clarity_html, height=0, width=0)
        st.session_state.clarity_enabled = True
    else:
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
