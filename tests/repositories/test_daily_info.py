"""DailyInfoRepository 테스트

일일 케어 기록 CRUD 및 배치 저장 로직 테스트.
향후 백엔드 API(/api/daily-records)로 분리 시 동일한 비즈니스 규칙이 적용됩니다.
"""

import pytest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock, call
from datetime import date
from modules.repositories.daily_info import DailyInfoRepository


class TestDailyInfoRepository:
    """DailyInfoRepository 테스트 클래스"""

    @pytest.fixture
    def repo(self):
        return DailyInfoRepository()

    @pytest.fixture
    def mock_execute_query(self):
        with patch.object(DailyInfoRepository, '_execute_query') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_query_one(self):
        with patch.object(DailyInfoRepository, '_execute_query_one') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_transaction(self):
        with patch.object(DailyInfoRepository, '_execute_transaction') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_transaction_lastrowid(self):
        with patch.object(DailyInfoRepository, '_execute_transaction_lastrowid') as mock:
            yield mock

    @pytest.fixture
    def sample_record(self):
        return {
            'customer_name': '홍길동',
            'customer_birth_date': '1950-01-01',
            'customer_grade': '3등급',
            'customer_recognition_no': 'L1234567890',
            'date': date(2024, 1, 15),
            'start_time': '09:00',
            'end_time': '18:00',
            'total_service_time': '9시간',
            'transport_service': '제공',
            'transport_vehicles': '차량',
            'hygiene_care': '완료',
            'bath_time': '10:00',
            'bath_method': '통목욕',
            'meal_breakfast': '일반식 전량',
            'meal_lunch': '일반식 전량',
            'meal_dinner': None,
            'toilet_care': '소변 3회 대변 1회',
            'mobility_care': '보행',
            'physical_note': '신체 특이사항 없음',
            'writer_phy': '홍담당',
            'cog_support': '완료',
            'comm_support': '완료',
            'cognitive_note': '인지 특이사항 없음',
            'writer_cog': '홍담당',
            'bp_temp': '120/80 36.5',
            'health_manage': '완료',
            'nursing_manage': '완료',
            'emergency': None,
            'nursing_note': None,
            'writer_nur': '홍담당',
            'prog_basic': '완료',
            'prog_activity': '완료',
            'prog_cognitive': '완료',
            'prog_therapy': '완료',
            'prog_enhance_detail': '인지활동프로그램',
            'functional_note': None,
            'writer_func': '홍담당'
        }

    # ========== find_existing_record_id 테스트 ==========

    def test_find_existing_record_id_exists(self, repo, mock_execute_query_one):
        """기존 레코드가 있을 때 record_id 반환"""
        mock_execute_query_one.return_value = {'record_id': 100}

        result = repo.find_existing_record_id(customer_id=1, record_date=date(2024, 1, 15))

        assert result == 100

    def test_find_existing_record_id_not_exists(self, repo, mock_execute_query_one):
        """기존 레코드가 없을 때 None 반환"""
        mock_execute_query_one.return_value = None

        result = repo.find_existing_record_id(customer_id=1, record_date=date(2024, 1, 15))

        assert result is None

    def test_find_existing_record_id_passes_params(self, repo, mock_execute_query_one):
        """올바른 파라미터가 전달되는지 확인"""
        mock_execute_query_one.return_value = None

        repo.find_existing_record_id(customer_id=5, record_date=date(2024, 3, 20))

        params = mock_execute_query_one.call_args[0][1]
        assert 5 in params
        assert date(2024, 3, 20) in params

    # ========== delete_daily_record 테스트 ==========

    def test_delete_daily_record_deletes_all_child_tables(self, repo):
        """삭제 시 모든 하위 테이블 레코드가 함께 삭제된다"""
        mock_cursor = MagicMock()
        executed_queries = []
        mock_cursor.execute.side_effect = lambda q, p: executed_queries.append(q)

        @contextmanager
        def _mock_transaction(dictionary=False):
            yield mock_cursor

        with patch('modules.repositories.daily_info.db_transaction', _mock_transaction):
            repo.delete_daily_record(record_id=100)

        assert any('daily_physicals' in q for q in executed_queries)
        assert any('daily_cognitives' in q for q in executed_queries)
        assert any('daily_nursings' in q for q in executed_queries)
        assert any('daily_recoveries' in q for q in executed_queries)
        assert any('daily_infos' in q for q in executed_queries)

    def test_delete_daily_record_none_record_id_skips(self, repo):
        """record_id가 None이면 아무것도 실행하지 않는다"""
        with patch('modules.repositories.daily_info.db_transaction') as mock_t:
            repo.delete_daily_record(record_id=None)

        mock_t.assert_not_called()

    def test_delete_daily_record_zero_record_id_skips(self, repo):
        """record_id가 0이면 아무것도 실행하지 않는다"""
        with patch('modules.repositories.daily_info.db_transaction') as mock_t:
            repo.delete_daily_record(record_id=0)

        mock_t.assert_not_called()

    def test_delete_daily_record_deletes_in_dependency_order(self, repo):
        """의존성 순서대로 삭제 (하위 테이블 먼저, daily_infos 마지막)"""
        mock_cursor = MagicMock()
        executed_queries = []
        mock_cursor.execute.side_effect = lambda q, p: executed_queries.append(q)

        @contextmanager
        def _mock_transaction(dictionary=False):
            yield mock_cursor

        with patch('modules.repositories.daily_info.db_transaction', _mock_transaction):
            repo.delete_daily_record(record_id=100)

        # daily_infos는 마지막에 삭제되어야 함
        daily_infos_idx = next(
            (i for i, q in enumerate(executed_queries) if 'daily_infos' in q), -1
        )
        assert daily_infos_idx == len(executed_queries) - 1

    # ========== insert_daily_info 테스트 ==========

    def test_insert_daily_info_returns_record_id(self, repo, mock_execute_transaction_lastrowid, sample_record):
        """새 daily_info 삽입 시 record_id 반환"""
        mock_execute_transaction_lastrowid.return_value = 101

        result = repo.insert_daily_info(customer_id=1, record=sample_record)

        assert result == 101

    def test_insert_daily_info_query_contains_insert(self, repo, mock_execute_transaction_lastrowid, sample_record):
        """INSERT 쿼리가 실행되는지 확인"""
        mock_execute_transaction_lastrowid.return_value = 1

        repo.insert_daily_info(customer_id=1, record=sample_record)

        query = mock_execute_transaction_lastrowid.call_args[0][0]
        assert 'INSERT' in query.upper()
        assert 'daily_infos' in query.lower()

    def test_insert_daily_info_passes_customer_id(self, repo, mock_execute_transaction_lastrowid, sample_record):
        """customer_id가 파라미터에 포함되는지 확인"""
        mock_execute_transaction_lastrowid.return_value = 1

        repo.insert_daily_info(customer_id=7, record=sample_record)

        params = mock_execute_transaction_lastrowid.call_args[0][1]
        assert 7 == params[0]

    # ========== get_customer_records 테스트 ==========

    def test_get_customer_records_without_date_filter(self, repo, mock_execute_query):
        """날짜 필터 없이 전체 레코드 조회"""
        expected = [{'record_id': 1, 'date': date(2024, 1, 15), 'physical_note': '정상'}]
        mock_execute_query.return_value = expected

        result = repo.get_customer_records(customer_id=1)

        assert len(result) == 1
        mock_execute_query.assert_called_once()

    def test_get_customer_records_with_date_range(self, repo, mock_execute_query):
        """날짜 범위로 레코드 필터링"""
        mock_execute_query.return_value = []

        repo.get_customer_records(
            customer_id=1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        call_args = mock_execute_query.call_args[0]
        params = call_args[1]
        assert date(2024, 1, 1) in params
        assert date(2024, 1, 31) in params

    def test_get_customer_records_returns_empty(self, repo, mock_execute_query):
        """레코드가 없을 때 빈 리스트 반환"""
        mock_execute_query.return_value = []

        result = repo.get_customer_records(customer_id=999)

        assert result == []

    def test_get_customer_records_ordered_desc(self, repo, mock_execute_query):
        """날짜 내림차순 정렬 확인"""
        mock_execute_query.return_value = []

        repo.get_customer_records(customer_id=1)

        query = mock_execute_query.call_args[0][0]
        assert 'DESC' in query.upper()

    # ========== get_record_by_customer_and_date 테스트 ==========

    def test_get_record_by_customer_and_date_exists(self, repo, mock_execute_query_one):
        """특정 날짜의 레코드 조회"""
        mock_execute_query_one.return_value = {'record_id': 55}

        result = repo.get_record_by_customer_and_date(
            customer_id=1,
            date=date(2024, 1, 15)
        )

        assert result == 55

    def test_get_record_by_customer_and_date_not_exists(self, repo, mock_execute_query_one):
        """해당 날짜에 레코드가 없을 때 None 반환"""
        mock_execute_query_one.return_value = None

        result = repo.get_record_by_customer_and_date(
            customer_id=1,
            date=date(2024, 12, 31)
        )

        assert result is None

    # ========== get_customers_with_records 테스트 ==========

    def test_get_customers_with_records_all(self, repo, mock_execute_query):
        """모든 기록이 있는 고객 목록 조회"""
        mock_execute_query.return_value = [
            {'customer_id': 1, 'name': '홍길동', 'record_count': 10}
        ]

        result = repo.get_customers_with_records()

        assert len(result) == 1

    def test_get_customers_with_records_date_filter(self, repo, mock_execute_query):
        """날짜 범위로 필터링된 고객 목록 조회"""
        mock_execute_query.return_value = []

        repo.get_customers_with_records(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        params = mock_execute_query.call_args[0][1]
        assert date(2024, 1, 1) in params
        assert date(2024, 1, 31) in params

    # ========== get_all_records_by_date_range 테스트 ==========

    def test_get_all_records_by_date_range(self, repo, mock_execute_query):
        """날짜 범위 내 모든 레코드 조회"""
        expected = [
            {'customer_name': '홍길동', 'record_id': 1, 'date': date(2024, 1, 15)}
        ]
        mock_execute_query.return_value = expected

        result = repo.get_all_records_by_date_range(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        assert len(result) == 1
        assert result[0]['customer_name'] == '홍길동'

    def test_get_all_records_by_date_range_passes_dates(self, repo, mock_execute_query):
        """날짜가 파라미터로 올바르게 전달되는지 확인"""
        mock_execute_query.return_value = []

        repo.get_all_records_by_date_range(
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 29)
        )

        params = mock_execute_query.call_args[0][1]
        assert date(2024, 2, 1) in params
        assert date(2024, 2, 29) in params

    # ========== save_parsed_data 테스트 ==========

    def test_save_parsed_data_empty_returns_zero(self, repo):
        """빈 레코드 목록은 0 반환"""
        result = repo.save_parsed_data(records=[])

        assert result == 0

    def test_save_parsed_data_calls_bulk_methods(self, repo, sample_record):
        """save_parsed_data가 bulk 메서드를 호출하는지 확인"""
        with patch.object(repo, '_bulk_get_or_create_customers', return_value={'홍길동': 1}) as mock_bulk_customers, \
             patch.object(repo, '_bulk_find_existing_records', return_value={}) as mock_bulk_records, \
             patch.object(repo, '_process_batch', return_value=1) as mock_batch:

            result = repo.save_parsed_data(records=[sample_record])

            mock_bulk_customers.assert_called_once()
            mock_bulk_records.assert_called_once()
            mock_batch.assert_called_once()
            assert result == 1

    def test_save_parsed_data_processes_in_batches(self, repo):
        """배치 단위로 처리하는지 확인 (메모리 최적화)"""
        records = [
            {
                'customer_name': f'고객{i}',
                'date': date(2024, 1, i % 28 + 1)
            }
            for i in range(25)
        ]

        with patch.object(repo, '_bulk_get_or_create_customers', return_value={f'고객{i}': i + 1 for i in range(25)}), \
             patch.object(repo, '_bulk_find_existing_records', return_value={}), \
             patch.object(repo, '_process_batch', return_value=20) as mock_batch:

            result = repo.save_parsed_data(records=records, batch_size=20)

            # 25개 레코드를 20씩 처리하면 2번 배치
            assert mock_batch.call_count == 2

    # ========== replace_daily_physicals 테스트 ==========

    def _make_mock_cursor(self):
        """쿼리 기록용 mock cursor 생성"""
        mock_cursor = MagicMock()
        executed_queries = []
        mock_cursor.execute.side_effect = lambda q, *args: executed_queries.append(q)
        mock_cursor._executed = executed_queries
        return mock_cursor

    def _mock_transaction_ctx(self, mock_cursor):
        """db_transaction 컨텍스트 매니저 mock 생성"""
        @contextmanager
        def _ctx(dictionary=False):
            yield mock_cursor
        return _ctx

    def test_replace_daily_physicals_deletes_then_inserts(self, repo, sample_record):
        """기존 데이터 삭제 후 새 데이터 삽입"""
        cursor = self._make_mock_cursor()
        with patch('modules.repositories.daily_info.db_transaction', self._mock_transaction_ctx(cursor)):
            repo.replace_daily_physicals(record_id=100, record=sample_record)

        assert any('DELETE' in q.upper() and 'daily_physicals' in q for q in cursor._executed)
        assert any('INSERT' in q.upper() and 'daily_physicals' in q for q in cursor._executed)

    def test_replace_daily_cognitives_deletes_then_inserts(self, repo, sample_record):
        """인지 데이터 교체: 삭제 후 삽입"""
        cursor = self._make_mock_cursor()
        with patch('modules.repositories.daily_info.db_transaction', self._mock_transaction_ctx(cursor)):
            repo.replace_daily_cognitives(record_id=100, record=sample_record)

        assert any('DELETE' in q.upper() and 'daily_cognitives' in q for q in cursor._executed)
        assert any('INSERT' in q.upper() and 'daily_cognitives' in q for q in cursor._executed)

    def test_replace_daily_nursings_deletes_then_inserts(self, repo, sample_record):
        """간호 데이터 교체: 삭제 후 삽입"""
        cursor = self._make_mock_cursor()
        with patch('modules.repositories.daily_info.db_transaction', self._mock_transaction_ctx(cursor)):
            repo.replace_daily_nursings(record_id=100, record=sample_record)

        assert any('DELETE' in q.upper() and 'daily_nursings' in q for q in cursor._executed)
        assert any('INSERT' in q.upper() and 'daily_nursings' in q for q in cursor._executed)

    def test_replace_daily_recoveries_deletes_then_inserts(self, repo, sample_record):
        """기능회복 데이터 교체: 삭제 후 삽입"""
        cursor = self._make_mock_cursor()
        with patch('modules.repositories.daily_info.db_transaction', self._mock_transaction_ctx(cursor)):
            repo.replace_daily_recoveries(record_id=100, record=sample_record)

        assert any('DELETE' in q.upper() and 'daily_recoveries' in q for q in cursor._executed)
        assert any('INSERT' in q.upper() and 'daily_recoveries' in q for q in cursor._executed)


class TestDailyInfoRepositoryHelpers:
    """DailyInfoRepository 내부 헬퍼 메서드 테스트"""

    @pytest.fixture
    def repo(self):
        return DailyInfoRepository()

    def test_bulk_get_or_create_customers_empty_names(self, repo):
        """고객명이 없으면 빈 딕셔너리 반환"""
        result = repo._bulk_get_or_create_customers(records=[], customer_names=[])

        assert result == {}

    def test_bulk_find_existing_records_empty_customer_map(self, repo):
        """고객 맵이 비어있으면 빈 딕셔너리 반환"""
        result = repo._bulk_find_existing_records(customer_map={}, records=[])

        assert result == {}
