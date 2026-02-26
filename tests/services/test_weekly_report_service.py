"""ReportService 테스트

주간 보고서 생성 비즈니스 로직 테스트.
향후 백엔드 API(/api/reports/weekly)로 분리 시 동일한 비즈니스 규칙이 적용됩니다.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from modules.services.weekly_report_service import ReportService


class TestReportService:
    """ReportService 테스트 클래스"""

    @pytest.fixture
    def service(self):
        return ReportService()

    @pytest.fixture
    def date_range(self):
        return (date(2024, 1, 8), date(2024, 1, 14))

    @pytest.fixture
    def sample_payload(self):
        return {
            'previous_week': {
                'physical': '[01-01] 신체 특이사항 없음\n[01-02] 보행 양호',
                'cognitive': '[01-01] 인지 정상\n[01-02] 대화 원활',
                'attendance': 3,
                'meals': {'일반식': 6.0, '죽식': 0.0, '다진식': 0.0},
                'toilet': {'소변': 9.0, '대변': 3.0, '기저귀교환': 0.0}
            },
            'current_week': {
                'physical': '[01-08] 신체 양호\n[01-09] 보행 보조',
                'cognitive': '[01-08] 인지 유지\n[01-09] 대화 활발',
                'attendance': 4,
                'meals': {'일반식': 8.0, '죽식': 0.0, '다진식': 0.0},
                'toilet': {'소변': 12.0, '대변': 4.0, '기저귀교환': 0.0}
            },
            'changes': {
                'meal': '2.0',
                'toilet': '4.0'
            },
            'previous_weekly_report': '지난 주 홍길동 어르신 상태 보고입니다.'
        }

    # ========== generate_weekly_report 테스트 ==========

    def test_generate_weekly_report_success(self, service, date_range, sample_payload):
        """AI 보고서 생성 성공"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "이번 주 홍길동 어르신의 상태 변화를 보고합니다."

        with patch('modules.services.weekly_report_service.get_ai_client', return_value=mock_client):
            mock_client.chat_completion.return_value = mock_response
            result = service.generate_weekly_report(
                customer_name='홍길동',
                date_range=date_range,
                analysis_payload=sample_payload
            )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "홍길동" in result or "보고" in result

    def test_generate_weekly_report_ai_error_returns_dict(self, service, date_range, sample_payload):
        """AI 오류 발생 시 에러 딕셔너리 반환"""
        with patch('modules.services.weekly_report_service.get_ai_client',
                   side_effect=Exception("API Error")):
            result = service.generate_weekly_report(
                customer_name='홍길동',
                date_range=date_range,
                analysis_payload=sample_payload
            )

        assert isinstance(result, dict)
        assert 'error' in result

    def test_generate_weekly_report_empty_response(self, service, date_range, sample_payload):
        """AI가 빈 응답을 반환할 때 에러 딕셔너리 반환"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = None

        with patch('modules.services.weekly_report_service.get_ai_client', return_value=mock_client):
            mock_client.chat_completion.return_value = mock_response
            result = service.generate_weekly_report(
                customer_name='홍길동',
                date_range=date_range,
                analysis_payload=sample_payload
            )

        assert isinstance(result, dict)
        assert 'error' in result

    def test_generate_weekly_report_strips_whitespace(self, service, date_range, sample_payload):
        """응답 텍스트의 앞뒤 공백이 제거된다"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  보고서 내용  \n"

        with patch('modules.services.weekly_report_service.get_ai_client', return_value=mock_client):
            mock_client.chat_completion.return_value = mock_response
            result = service.generate_weekly_report(
                customer_name='홍길동',
                date_range=date_range,
                analysis_payload=sample_payload
            )

        assert result == "보고서 내용"

    def test_generate_weekly_report_uses_openai(self, service, date_range, sample_payload):
        """주간 보고서는 OpenAI 클라이언트를 사용한다"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "보고서"

        with patch('modules.services.weekly_report_service.get_ai_client',
                   return_value=mock_client) as mock_get_client:
            mock_client.chat_completion.return_value = mock_response
            service.generate_weekly_report(
                customer_name='홍길동',
                date_range=date_range,
                analysis_payload=sample_payload
            )

        mock_get_client.assert_called_once_with(provider='openai')

    # ========== _format_input_data 테스트 ==========

    def test_format_input_data_includes_customer_name(self, service, date_range, sample_payload):
        """입력 데이터에 고객명이 포함된다"""
        result = service._format_input_data('홍길동', date_range, sample_payload)

        assert '홍길동' in result

    def test_format_input_data_includes_date_range(self, service, date_range, sample_payload):
        """입력 데이터에 날짜 범위가 포함된다"""
        result = service._format_input_data('홍길동', date_range, sample_payload)

        assert '2024-01-08' in result
        assert '2024-01-14' in result

    def test_format_input_data_empty_payload(self, service, date_range):
        """빈 페이로드도 처리 가능"""
        result = service._format_input_data('홍길동', date_range, {})

        assert isinstance(result, str)
        assert '홍길동' in result

    def test_format_input_data_none_payload(self, service, date_range):
        """None 페이로드도 처리 가능 (안전한 기본값 사용)"""
        result = service._format_input_data('홍길동', date_range, None)

        assert isinstance(result, str)

    def test_format_input_data_handles_missing_keys(self, service, date_range):
        """페이로드에 일부 키가 없어도 처리 가능"""
        partial_payload = {
            'previous_week': {'physical': '신체 정상'},
            # current_week, changes 등 누락
        }

        result = service._format_input_data('홍길동', date_range, partial_payload)

        assert isinstance(result, str)


class TestReportServiceInternalHelpers:
    """ReportService 내부 헬퍼 함수 테스트 (순수 로직)"""

    @pytest.fixture
    def service(self):
        return ReportService()

    def test_format_to_float_integer(self, service):
        """정수 값을 float으로 변환"""
        # _format_input_data 내부 _to_float 로직 간접 테스트
        payload = {'changes': {'meal': 5, 'toilet': 3}}
        result = service._format_input_data(
            '테스트',
            (date(2024, 1, 8), date(2024, 1, 14)),
            {'previous_week': {}, 'current_week': {}, 'changes': payload['changes']}
        )
        assert isinstance(result, str)

    def test_format_with_missing_values(self, service):
        """없음 값이 처리되는지 확인"""
        payload = {
            'previous_week': {'physical': None, 'cognitive': ''},
            'current_week': {'physical': '정상', 'cognitive': None},
            'changes': {'meal': None, 'toilet': '-'}
        }
        result = service._format_input_data(
            '홍길동',
            (date(2024, 1, 8), date(2024, 1, 14)),
            payload
        )
        # 예외 없이 처리됨
        assert isinstance(result, str)
