"""WeeklyStatusRepository 테스트

주간 상태 보고서 저장/조회 데이터 액세스 레이어 테스트.
향후 백엔드 API(/api/weekly-status)로 분리 시 동일한 비즈니스 규칙이 적용됩니다.
"""

import pytest
from unittest.mock import patch
from datetime import date
from modules.repositories.weekly_status import WeeklyStatusRepository


class TestWeeklyStatusRepository:
    """WeeklyStatusRepository 테스트 클래스"""

    @pytest.fixture
    def repo(self):
        return WeeklyStatusRepository()

    @pytest.fixture
    def mock_execute_query(self):
        with patch.object(WeeklyStatusRepository, '_execute_query') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_query_one(self):
        with patch.object(WeeklyStatusRepository, '_execute_query_one') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_transaction(self):
        with patch.object(WeeklyStatusRepository, '_execute_transaction') as mock:
            yield mock

    @pytest.fixture
    def sample_report_text(self):
        return "이번 주 홍길동 어르신의 상태 변화를 보고합니다. 신체 상태 양호, 인지 상태 유지."

    # ========== save_weekly_status 테스트 ==========

    def test_save_weekly_status_new_record(self, repo, mock_execute_transaction, sample_report_text):
        """새 주간 보고서 저장"""
        mock_execute_transaction.return_value = 1

        repo.save_weekly_status(
            customer_id=1,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14),
            report_text=sample_report_text
        )

        mock_execute_transaction.assert_called_once()
        query, params = mock_execute_transaction.call_args[0]
        assert 'INSERT' in query.upper()
        assert 'weekly_status' in query.lower()

    def test_save_weekly_status_uses_upsert(self, repo, mock_execute_transaction, sample_report_text):
        """기존 보고서가 있으면 UPDATE하는 UPSERT 쿼리 사용"""
        mock_execute_transaction.return_value = 1

        repo.save_weekly_status(
            customer_id=1,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14),
            report_text=sample_report_text
        )

        query = mock_execute_transaction.call_args[0][0]
        # ON DUPLICATE KEY UPDATE 또는 UPSERT 패턴
        assert 'ON DUPLICATE KEY UPDATE' in query.upper() or 'INSERT OR REPLACE' in query.upper()

    def test_save_weekly_status_params_order(self, repo, mock_execute_transaction, sample_report_text):
        """파라미터가 올바른 순서로 전달되는지 확인"""
        mock_execute_transaction.return_value = 1

        repo.save_weekly_status(
            customer_id=5,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14),
            report_text=sample_report_text
        )

        params = mock_execute_transaction.call_args[0][1]
        assert params[0] == 5  # customer_id 첫 번째
        assert sample_report_text in params

    # ========== load_weekly_status 테스트 ==========

    def test_load_weekly_status_exists(self, repo, mock_execute_query_one, sample_report_text):
        """보고서가 있을 때 텍스트 반환"""
        mock_execute_query_one.return_value = {'report_text': sample_report_text}

        result = repo.load_weekly_status(
            customer_id=1,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14)
        )

        assert result == sample_report_text

    def test_load_weekly_status_not_exists(self, repo, mock_execute_query_one):
        """보고서가 없을 때 None 반환"""
        mock_execute_query_one.return_value = None

        result = repo.load_weekly_status(
            customer_id=999,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14)
        )

        assert result is None

    def test_load_weekly_status_passes_correct_params(self, repo, mock_execute_query_one):
        """올바른 파라미터로 쿼리 실행"""
        mock_execute_query_one.return_value = None

        repo.load_weekly_status(
            customer_id=7,
            start_date=date(2024, 2, 5),
            end_date=date(2024, 2, 11)
        )

        params = mock_execute_query_one.call_args[0][1]
        assert 7 in params
        assert date(2024, 2, 5) in params
        assert date(2024, 2, 11) in params

    # ========== get_all_by_customer 테스트 ==========

    def test_get_all_by_customer_with_results(self, repo, mock_execute_query, sample_report_text):
        """고객의 모든 주간 보고서 조회"""
        mock_execute_query.return_value = [
            {
                'start_date': date(2024, 1, 8),
                'end_date': date(2024, 1, 14),
                'report_text': sample_report_text,
                'created_at': '2024-01-15 10:00:00',
                'updated_at': '2024-01-15 10:00:00'
            }
        ]

        result = repo.get_all_by_customer(customer_id=1)

        assert len(result) == 1
        assert result[0]['report_text'] == sample_report_text

    def test_get_all_by_customer_empty(self, repo, mock_execute_query):
        """보고서가 없는 고객"""
        mock_execute_query.return_value = []

        result = repo.get_all_by_customer(customer_id=999)

        assert result == []

    def test_get_all_by_customer_default_limit(self, repo, mock_execute_query):
        """기본 limit(10) 적용 확인"""
        mock_execute_query.return_value = []

        repo.get_all_by_customer(customer_id=1)

        params = mock_execute_query.call_args[0][1]
        assert 10 in params  # 기본 limit

    def test_get_all_by_customer_custom_limit(self, repo, mock_execute_query):
        """커스텀 limit 적용 확인"""
        mock_execute_query.return_value = []

        repo.get_all_by_customer(customer_id=1, limit=5)

        params = mock_execute_query.call_args[0][1]
        assert 5 in params

    def test_get_all_by_customer_ordered_desc(self, repo, mock_execute_query):
        """최신 보고서부터 내림차순 정렬 확인"""
        mock_execute_query.return_value = []

        repo.get_all_by_customer(customer_id=1)

        query = mock_execute_query.call_args[0][0]
        assert 'DESC' in query.upper()
        assert 'ORDER BY' in query.upper()

    # ========== delete_weekly_status 테스트 ==========

    def test_delete_weekly_status_success(self, repo, mock_execute_transaction):
        """주간 보고서 삭제 성공"""
        mock_execute_transaction.return_value = 1

        result = repo.delete_weekly_status(
            customer_id=1,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14)
        )

        assert result == 1

    def test_delete_weekly_status_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 보고서 삭제 시 0 반환"""
        mock_execute_transaction.return_value = 0

        result = repo.delete_weekly_status(
            customer_id=999,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14)
        )

        assert result == 0

    def test_delete_weekly_status_query_is_delete(self, repo, mock_execute_transaction):
        """DELETE 쿼리가 실행되는지 확인"""
        mock_execute_transaction.return_value = 1

        repo.delete_weekly_status(
            customer_id=1,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 14)
        )

        query = mock_execute_transaction.call_args[0][0]
        assert 'DELETE' in query.upper()
        assert 'weekly_status' in query.lower()

    def test_delete_weekly_status_passes_all_params(self, repo, mock_execute_transaction):
        """삭제 쿼리에 모든 파라미터가 전달되는지 확인"""
        mock_execute_transaction.return_value = 1

        repo.delete_weekly_status(
            customer_id=3,
            start_date=date(2024, 3, 4),
            end_date=date(2024, 3, 10)
        )

        params = mock_execute_transaction.call_args[0][1]
        assert 3 in params
        assert date(2024, 3, 4) in params
        assert date(2024, 3, 10) in params
