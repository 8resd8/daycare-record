"""OpenAI 클라이언트 관리 모듈"""

import openai
import streamlit as st


class AIClient:
    """OpenAI 클라이언트 래퍼 클래스"""
    
    def __init__(self, client: openai.OpenAI):
        self._client = client
    
    @property
    def client(self) -> openai.OpenAI:
        """OpenAI 클라이언트 인스턴스 반환"""
        return self._client
    
    def chat_completion(self, model: str, messages: list, **kwargs):
        """채팅 완성 요청"""
        return self._client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )


@st.cache_resource
def get_ai_client() -> AIClient:
    """캐시된 AI 클라이언트 인스턴스 반환
    
    Streamlit의 캐시를 사용하여 앱 재실행 시에도 동일한 클라이언트 재사용
    """
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API 키가 설정되어 있지 않습니다.")
    
    client = openai.OpenAI(api_key=api_key)
    return AIClient(client)
