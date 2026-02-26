"""BaseRepository 테스트

향후 React/백엔드 분리 시 데이터 액세스 레이어의 기본 동작을 검증합니다.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager
from modules.repositories.base import BaseRepository


class TestBaseRepository:
    """BaseRepository 메서드 테스트 (DB mock 사용)"""

    @pytest.fixture
    def repo(self):
        return BaseRepository()

    @pytest.fixture
    def mock_cursor(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        cursor.rowcount = 0
        cursor.lastrowid = 0
        return cursor

    @pytest.fixture
    def mock_db_ctx(self, mock_cursor):
        """db_query와 db_transaction 컨텍스트 매니저 mock"""
        @contextmanager
        def _mock_query(dictionary=True):
            yield mock_cursor

        @contextmanager
        def _mock_transaction(dictionary=False):
            yield mock_cursor

        with patch('modules.repositories.base.db_query', _mock_query), \
             patch('modules.repositories.base.db_transaction', _mock_transaction):
            yield mock_cursor

    # ========== _execute_query 테스트 ==========

    def test_execute_query_returns_all_results(self, repo, mock_db_ctx):
        """_execute_query는 fetchall() 결과를 반환한다"""
        expected = [{'id': 1, 'name': '홍길동'}, {'id': 2, 'name': '김철수'}]
        mock_db_ctx.fetchall.return_value = expected

        result = repo._execute_query("SELECT * FROM customers")

        assert result == expected

    def test_execute_query_with_params(self, repo, mock_db_ctx):
        """파라미터와 함께 _execute_query 실행"""
        mock_db_ctx.fetchall.return_value = [{'id': 1}]

        repo._execute_query("SELECT * FROM customers WHERE id = %s", (1,))

        mock_db_ctx.execute.assert_called_once_with(
            "SELECT * FROM customers WHERE id = %s", (1,)
        )

    def test_execute_query_returns_empty_list(self, repo, mock_db_ctx):
        """결과가 없을 때 빈 리스트 반환"""
        mock_db_ctx.fetchall.return_value = []

        result = repo._execute_query("SELECT * FROM customers WHERE 1=0")

        assert result == []

    def test_execute_query_without_params(self, repo, mock_db_ctx):
        """파라미터 없이 _execute_query 실행 (빈 튜플 사용)"""
        mock_db_ctx.fetchall.return_value = []

        repo._execute_query("SELECT 1")

        mock_db_ctx.execute.assert_called_once_with("SELECT 1", ())

    # ========== _execute_query_one 테스트 ==========

    def test_execute_query_one_returns_single_result(self, repo, mock_db_ctx):
        """_execute_query_one은 fetchone() 결과를 반환한다"""
        expected = {'id': 1, 'name': '홍길동'}
        mock_db_ctx.fetchone.return_value = expected

        result = repo._execute_query_one("SELECT * FROM customers WHERE id = %s", (1,))

        assert result == expected

    def test_execute_query_one_returns_none(self, repo, mock_db_ctx):
        """결과가 없을 때 None 반환"""
        mock_db_ctx.fetchone.return_value = None

        result = repo._execute_query_one("SELECT * FROM customers WHERE id = %s", (999,))

        assert result is None

    def test_execute_query_one_calls_fetchone(self, repo, mock_db_ctx):
        """fetchone()이 호출되는지 확인"""
        mock_db_ctx.fetchone.return_value = None

        repo._execute_query_one("SELECT 1")

        mock_db_ctx.fetchone.assert_called_once()

    # ========== _execute_transaction 테스트 ==========

    def test_execute_transaction_returns_rowcount(self, repo, mock_db_ctx):
        """_execute_transaction은 영향받은 행 수를 반환한다"""
        mock_db_ctx.rowcount = 2

        result = repo._execute_transaction("UPDATE customers SET name=%s WHERE 1=1", ('테스트',))

        assert result == 2

    def test_execute_transaction_calls_execute(self, repo, mock_db_ctx):
        """execute()가 호출되는지 확인"""
        mock_db_ctx.rowcount = 1

        repo._execute_transaction(
            "INSERT INTO customers (name) VALUES (%s)",
            ('홍길동',)
        )

        mock_db_ctx.execute.assert_called_once_with(
            "INSERT INTO customers (name) VALUES (%s)", ('홍길동',)
        )

    def test_execute_transaction_without_params(self, repo, mock_db_ctx):
        """파라미터 없이 트랜잭션 실행"""
        mock_db_ctx.rowcount = 3

        repo._execute_transaction("DELETE FROM temp_table")

        mock_db_ctx.execute.assert_called_once_with("DELETE FROM temp_table", ())

    def test_execute_transaction_delete_returns_rowcount(self, repo, mock_db_ctx):
        """DELETE 쿼리의 rowcount 반환"""
        mock_db_ctx.rowcount = 5

        result = repo._execute_transaction("DELETE FROM logs WHERE created_at < %s", ('2024-01-01',))

        assert result == 5

    # ========== _execute_transaction_lastrowid 테스트 ==========

    def test_execute_transaction_lastrowid_returns_new_id(self, repo, mock_db_ctx):
        """_execute_transaction_lastrowid는 새로 생성된 행의 ID를 반환한다"""
        mock_db_ctx.lastrowid = 42

        result = repo._execute_transaction_lastrowid(
            "INSERT INTO customers (name) VALUES (%s)",
            ('홍길동',)
        )

        assert result == 42

    def test_execute_transaction_lastrowid_calls_execute(self, repo, mock_db_ctx):
        """execute()가 올바른 쿼리로 호출되는지 확인"""
        mock_db_ctx.lastrowid = 10

        repo._execute_transaction_lastrowid(
            "INSERT INTO daily_infos (customer_id, date) VALUES (%s, %s)",
            (1, '2024-01-15')
        )

        mock_db_ctx.execute.assert_called_once_with(
            "INSERT INTO daily_infos (customer_id, date) VALUES (%s, %s)",
            (1, '2024-01-15')
        )

    # ========== _execute_transaction_many 테스트 ==========

    def test_execute_transaction_many_calls_executemany(self, repo, mock_db_ctx):
        """executemany()가 호출되는지 확인"""
        mock_db_ctx.rowcount = 3
        params_list = [('홍길동',), ('김철수',), ('이영희',)]
        query = "INSERT INTO customers (name) VALUES (%s)"

        repo._execute_transaction_many(query, params_list)

        mock_db_ctx.executemany.assert_called_once_with(query, params_list)

    def test_execute_transaction_many_returns_rowcount(self, repo, mock_db_ctx):
        """rowcount 반환 확인"""
        mock_db_ctx.rowcount = 3
        params_list = [('홍길동',), ('김철수',), ('이영희',)]

        result = repo._execute_transaction_many(
            "INSERT INTO customers (name) VALUES (%s)",
            params_list
        )

        assert result == 3

    def test_execute_transaction_many_empty_list(self, repo, mock_db_ctx):
        """빈 리스트로 executemany 실행"""
        mock_db_ctx.rowcount = 0

        repo._execute_transaction_many("INSERT INTO customers (name) VALUES (%s)", [])

        mock_db_ctx.executemany.assert_called_once()
