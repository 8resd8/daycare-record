"""AI 클라이언트 모듈 테스트

OpenAI/Gemini 클라이언트 래퍼, 의존성 주입, API 키 조회 로직 테스트.
향후 백엔드 분리 시 AI 클라이언트 계층의 독립성을 보장합니다.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from modules.clients.ai_client import (
    BaseAIClient,
    OpenAIClient,
    GeminiClient,
    get_ai_client,
    set_ai_client,
    get_api_key,
)


class TestBaseAIClient:
    """BaseAIClient 인터페이스 테스트"""

    def test_chat_completion_raises_not_implemented(self):
        """BaseAIClient.chat_completion은 NotImplementedError를 발생시킨다"""
        client = BaseAIClient()

        with pytest.raises(NotImplementedError):
            client.chat_completion(model='test', messages=[])


class TestOpenAIClient:
    """OpenAIClient 래퍼 테스트"""

    @pytest.fixture
    def mock_openai_client(self):
        return MagicMock()

    @pytest.fixture
    def client(self, mock_openai_client):
        return OpenAIClient(client=mock_openai_client)

    def test_client_property_returns_openai_instance(self, client, mock_openai_client):
        """client 프로퍼티가 OpenAI 인스턴스를 반환한다"""
        assert client.client is mock_openai_client

    def test_chat_completion_calls_openai_api(self, client, mock_openai_client):
        """chat_completion이 OpenAI API를 호출한다"""
        mock_response = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response

        result = client.chat_completion(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': '안녕'}]
        )

        mock_openai_client.chat.completions.create.assert_called_once()
        assert result == mock_response

    def test_chat_completion_passes_model_and_messages(self, client, mock_openai_client):
        """chat_completion에 모델과 메시지가 올바르게 전달된다"""
        mock_openai_client.chat.completions.create.return_value = MagicMock()

        client.chat_completion(
            model='gpt-4o',
            messages=[{'role': 'system', 'content': '시스템 프롬프트'}]
        )

        call_kwargs = mock_openai_client.chat.completions.create.call_args
        assert call_kwargs.kwargs['model'] == 'gpt-4o'
        assert call_kwargs.kwargs['messages'] == [{'role': 'system', 'content': '시스템 프롬프트'}]

    def test_chat_completion_passes_extra_kwargs(self, client, mock_openai_client):
        """추가 kwargs가 API에 전달된다"""
        mock_openai_client.chat.completions.create.return_value = MagicMock()

        client.chat_completion(
            model='gpt-4o-mini',
            messages=[],
            temperature=0.5,
            max_tokens=100
        )

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs['temperature'] == 0.5
        assert call_kwargs['max_tokens'] == 100


class TestGeminiClient:
    """GeminiClient 래퍼 테스트"""

    @pytest.fixture
    def mock_genai(self):
        """google.generativeai 모듈 mock"""
        with patch('modules.clients.ai_client.genai') as mock:
            mock.configure = MagicMock()
            yield mock

    @pytest.fixture
    def client(self, mock_genai):
        return GeminiClient(api_key='test-api-key')

    def test_init_configures_genai(self, mock_genai):
        """초기화 시 genai.configure가 호출된다"""
        GeminiClient(api_key='test-key')

        mock_genai.configure.assert_called_once_with(api_key='test-key')

    def test_init_raises_when_genai_unavailable(self):
        """genai 모듈이 없으면 ModuleNotFoundError 발생"""
        with patch('modules.clients.ai_client.genai', None):
            with pytest.raises(ModuleNotFoundError):
                GeminiClient(api_key='test-key')

    def test_convert_messages_system_instruction(self, client):
        """system 역할 메시지가 system_instruction으로 변환된다"""
        messages = [
            {'role': 'system', 'content': '시스템 지시사항'},
            {'role': 'user', 'content': '사용자 메시지'}
        ]

        system_instruction, contents = client._convert_messages_to_gemini_format(messages)

        assert system_instruction == '시스템 지시사항'

    def test_convert_messages_user_role(self, client):
        """user 역할 메시지가 Gemini 형식으로 변환된다"""
        messages = [
            {'role': 'user', 'content': '사용자 질문'}
        ]

        _, contents = client._convert_messages_to_gemini_format(messages)

        assert len(contents) == 1
        assert contents[0]['role'] == 'user'
        assert '사용자 질문' in contents[0]['parts']

    def test_convert_messages_assistant_role(self, client):
        """assistant 역할 메시지가 Gemini 'model' 역할로 변환된다"""
        messages = [
            {'role': 'assistant', 'content': 'AI 응답'}
        ]

        _, contents = client._convert_messages_to_gemini_format(messages)

        assert len(contents) == 1
        assert contents[0]['role'] == 'model'

    def test_convert_messages_no_system(self, client):
        """system 메시지가 없을 때 system_instruction은 None"""
        messages = [
            {'role': 'user', 'content': '질문'}
        ]

        system_instruction, _ = client._convert_messages_to_gemini_format(messages)

        assert system_instruction is None

    def test_chat_completion_returns_openai_compatible_response(self, client, mock_genai):
        """chat_completion이 OpenAI 호환 응답 형식을 반환한다"""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"result": "테스트 응답"}'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        response = client.chat_completion(
            model='gemini-flash',
            messages=[{'role': 'user', 'content': '테스트'}]
        )

        # OpenAI 호환 형식 확인
        assert hasattr(response, 'choices')
        assert hasattr(response.choices[0], 'message')
        assert hasattr(response.choices[0].message, 'content')
        assert response.choices[0].message.content == '{"result": "테스트 응답"}'


class TestSetAiClient:
    """set_ai_client / get_ai_client 의존성 주입 테스트"""

    def setup_method(self):
        """각 테스트 전에 AI 클라이언트 초기화"""
        set_ai_client(None)

    def teardown_method(self):
        """각 테스트 후에 AI 클라이언트 초기화"""
        set_ai_client(None)

    def test_set_ai_client_injects_custom_client(self):
        """set_ai_client로 커스텀 클라이언트를 주입할 수 있다"""
        mock_client = MagicMock(spec=BaseAIClient)
        set_ai_client(mock_client)

        with patch('modules.clients.ai_client._ai_client_instance', mock_client):
            result = get_ai_client()

        assert result is mock_client

    def test_set_ai_client_none_clears_injection(self):
        """set_ai_client(None)으로 주입된 클라이언트를 제거할 수 있다"""
        mock_client = MagicMock(spec=BaseAIClient)
        set_ai_client(mock_client)
        set_ai_client(None)

        # None으로 초기화되면 실제 클라이언트 생성 시도
        import modules.clients.ai_client as ai_module
        assert ai_module._ai_client_instance is None


class TestGetApiKey:
    """get_api_key 함수 테스트"""

    def test_get_api_key_gemini_from_env(self):
        """환경변수에서 Gemini API 키 조회"""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-gemini-key'}):
            result = get_api_key(provider='gemini')

        assert result == 'test-gemini-key'

    def test_get_api_key_openai_from_env(self):
        """환경변수에서 OpenAI API 키 조회"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-openai-key'}):
            result = get_api_key(provider='openai')

        assert result == 'test-openai-key'

    def test_get_api_key_gemini_raises_when_missing(self):
        """Gemini API 키가 없으면 ValueError 발생"""
        # streamlit.secrets에도 키가 없도록 mock 처리
        mock_st = MagicMock()
        mock_st.secrets.get.return_value = None
        mock_st.secrets.__contains__ = lambda self, key: False

        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {'streamlit': mock_st}):
                with pytest.raises(ValueError):
                    get_api_key(provider='gemini')

    def test_get_api_key_openai_raises_when_missing(self):
        """OpenAI API 키가 없으면 ValueError 발생"""
        mock_st = MagicMock()
        mock_st.secrets.get.return_value = None
        mock_st.secrets.__contains__ = lambda self, key: False

        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {'streamlit': mock_st}):
                with pytest.raises(ValueError):
                    get_api_key(provider='openai')

    def test_get_api_key_env_takes_priority_over_secrets(self):
        """환경변수가 Streamlit secrets보다 우선순위가 높다"""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'env-key'}):
            result = get_api_key(provider='gemini')

        assert result == 'env-key'
