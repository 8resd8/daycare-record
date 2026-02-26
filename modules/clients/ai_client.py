"""AI 클라이언트 관리 모듈

이 모듈은 다음을 지원하는 AI 클라이언트 관리 기능을 제공합니다:
- OpenAI API (GPT 모델)
- Google Gemini API
- Streamlit secrets (프로덕션용)
- 환경변수 (테스트/CLI용)
- 의존성 주입 (단위 테스트용)
- Rate Limit 재시도 로직 (tenacity)
"""

import os
import openai
from typing import Optional, Any, List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import google.generativeai as genai
except ModuleNotFoundError:  # pragma: no cover
    genai = None

# AI Client instance for dependency injection (테스트용)
_ai_client_instance: Optional['BaseAIClient'] = None


class BaseAIClient:
    """AI 클라이언트 기본 인터페이스"""
    
    def chat_completion(self, model: str, messages: list, **kwargs):
        """채팅 완성 요청"""
        raise NotImplementedError


class OpenAIClient(BaseAIClient):
    """OpenAI 클라이언트 래퍼 클래스"""
    
    def __init__(self, client: openai.OpenAI):
        self._client = client
    
    @property
    def client(self) -> openai.OpenAI:
        """OpenAI 클라이언트 인스턴스 반환"""
        return self._client
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type(openai.RateLimitError),
        before_sleep=lambda retry_state: print(f"Rate limit reached. Retrying in {retry_state.next_action.sleep} seconds... (Attempt {retry_state.attempt_number}/5)")
    )
    def chat_completion(self, model: str, messages: list, **kwargs):
        """채팅 완성 요청 (Rate Limit 자동 재시도 포함)"""
        return self._client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )


class GeminiClient(BaseAIClient):
    """Google Gemini 클라이언트 래퍼 클래스"""
    
    def __init__(self, api_key: str):
        if genai is None:
            raise ModuleNotFoundError(
                "google-generativeai 패키지가 설치되어 있지 않습니다. "
                "Gemini를 사용하려면 requirements.txt의 google-generativeai를 설치하세요."
            )

        genai.configure(api_key=api_key)
        self._api_key = api_key
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> tuple:
        """OpenAI 메시지 형식을 Gemini 형식으로 변환
        
        Args:
            messages: OpenAI 형식의 메시지 리스트
            
        Returns:
            (system_instruction, contents) 튜플
        """
        system_instruction = None
        contents = []
        
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')
            
            if role == 'system':
                system_instruction = content
            elif role == 'user':
                contents.append({'role': 'user', 'parts': [content]})
            elif role == 'assistant':
                contents.append({'role': 'model', 'parts': [content]})
        
        return system_instruction, contents
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        before_sleep=lambda retry_state: print(f"Rate limit reached. Retrying in {retry_state.next_action.sleep} seconds... (Attempt {retry_state.attempt_number}/5)")
    )
    def chat_completion(self, model: str, messages: list, **kwargs):
        # Gemini API

        system_instruction, contents = self._convert_messages_to_gemini_format(messages)
        
        generation_config = {
            'temperature': kwargs.get('temperature', 0.7),
            'response_mime_type': 'application/json'
        }
        
        gemini_model = genai.GenerativeModel(
            model_name='gemini-3-flash-preview',
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        
        response = gemini_model.generate_content(contents)
        
        class GeminiResponse:
            def __init__(self, text):
                self.choices = [type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'content': text
                    })()
                })()]
        
        return GeminiResponse(response.text)


def set_ai_client(client: Optional[Any]) -> None:
    # 테스트용 커스텀 AI 클라이언트 설정
    global _ai_client_instance
    _ai_client_instance = client


def get_api_key(provider: str = 'gemini') -> str:
    if provider == 'gemini':
        env_key = 'GEMINI_API_KEY'
        secret_key = 'GEMINI_API_KEY'
        error_msg = "Gemini API 키가 설정되어 있지 않습니다. 환경변수 또는 Streamlit secrets를 설정하세요."
    else:
        env_key = 'OPENAI_API_KEY'
        secret_key = 'OPENAI_API_KEY'
        error_msg = "OpenAI API 키가 설정되어 있지 않습니다. 환경변수 또는 Streamlit secrets를 설정하세요."
    
    # 환경변수에서 확인
    api_key = os.environ.get(env_key)
    if api_key:
        return api_key
    
    # Streamlit secrets에서 확인
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            api_key = st.secrets.get(secret_key)
            if api_key:
                return api_key
    except (ImportError, RuntimeError):
        pass
    
    raise ValueError(error_msg)


def get_ai_client(provider: str = 'gemini') -> BaseAIClient:
    """AI 클라이언트 인스턴스 반환
    
    Args:
        provider: 'openai' 또는 'gemini' (기본값: 'gemini')
    
    설정된 커스텀 클라이언트가 있으면 사용하고(테스트용),
    그렇지 않으면 환경변수나 Streamlit secrets의 API 키로 새 클라이언트를 생성합니다.
    
    Streamlit 프로덕션 환경에서는 st.cache_resource를 사용하여 캐시됩니다.
    """
    global _ai_client_instance
    
    # 테스트용 커스텀 클라이언트가 설정되어 있으면 반환
    if _ai_client_instance is not None:
        return _ai_client_instance
    
    # Streamlit 환경인 경우 캐시된 클라이언트 반환
    try:
        import streamlit as st
        return _get_cached_ai_client(provider)
    except (ImportError, RuntimeError):
        pass
    
    # 일반 환경에서는 새 클라이언트 생성
    api_key = get_api_key(provider)
    if provider == 'gemini':
        if genai is None:
            raise ModuleNotFoundError(
                "google-generativeai 패키지가 설치되어 있지 않습니다. "
                "Gemini를 사용하려면 requirements.txt의 google-generativeai를 설치하세요."
            )
        return GeminiClient(api_key)
    else:
        client = openai.OpenAI(api_key=api_key)
        return OpenAIClient(client)


def _get_cached_ai_client(provider: str = 'gemini') -> BaseAIClient:
    import streamlit as st
    
    @st.cache_resource
    def _create_client(prov: str):
        api_key = get_api_key(prov)
        if prov == 'gemini':
            if genai is None:
                raise ModuleNotFoundError(
                    "google-generativeai 패키지가 설치되어 있지 않습니다. "
                    "Gemini를 사용하려면 requirements.txt의 google-generativeai를 설치하세요."
                )
            return GeminiClient(api_key)
        else:
            client = openai.OpenAI(api_key=api_key)
            return OpenAIClient(client)
    
    return _create_client(provider)
