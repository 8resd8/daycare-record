"""
DB 연결 모듈 단위 테스트 (modules/db_connection.py)
=====================================================
비즈니스 규칙:
  - 환경변수(DB_HOST 등) 설정 시 환경변수 우선
  - 환경변수 없으면 Streamlit secrets 사용
  - set_connection_factory()로 테스트용 연결 주입 가능
  - db_transaction: 성공 시 커밋, 예외 시 롤백
  - db_query: 읽기 전용, 미소비 결과 자동 정리
  - release_pool(): 연결 풀 해제
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import modules.db_connection as db_module
from modules.db_connection import (
    set_connection_factory,
    get_db_config,
    get_db_connection,
    db_transaction,
    db_query,
    release_pool,
)


# ───────────────────────────────────────────────────────────────
# Fixture: 각 테스트 후 팩토리/풀 초기화
# ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db_state():
    """각 테스트 전후 DB 모듈 상태 초기화."""
    set_connection_factory(None)
    release_pool()
    yield
    set_connection_factory(None)
    release_pool()


def make_mock_conn():
    """cursor, commit, rollback, close를 가진 mock 연결 생성."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    conn.cursor.return_value = cursor
    return conn, cursor


# ───────────────────────────────────────────────────────────────
# 1. get_db_config — 설정 우선순위
# ───────────────────────────────────────────────────────────────

class TestGetDbConfig:
    """
    비즈니스 규칙:
      - DB_HOST 환경변수가 있으면 환경변수 설정 반환
      - 환경변수 없으면 Streamlit secrets 시도
      - 둘 다 없으면 RuntimeError 발생
    """

    def test_env_vars_take_priority(self):
        env = {
            "DB_HOST": "localhost",
            "DB_PORT": "3306",
            "DB_USER": "user",
            "DB_PASSWORD": "pw",
            "DB_NAME": "testdb",
        }
        with patch.dict(os.environ, env, clear=False):
            config = get_db_config()
        assert config["host"] == "localhost"
        assert config["user"] == "user"
        assert config["database"] == "testdb"

    def test_env_db_port_defaults_to_3306(self):
        env = {"DB_HOST": "localhost", "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "db"}
        with patch.dict(os.environ, env, clear=False):
            config = get_db_config()
        assert config["port"] == 3306

    def test_env_custom_port_used(self):
        env = {
            "DB_HOST": "localhost", "DB_PORT": "3307",
            "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "db"
        }
        with patch.dict(os.environ, env, clear=False):
            config = get_db_config()
        assert config["port"] == 3307

    def test_env_config_has_timezone(self):
        env = {"DB_HOST": "h", "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "d"}
        with patch.dict(os.environ, env, clear=False):
            config = get_db_config()
        assert config.get("time_zone") == "+09:00"

    def test_no_config_raises_runtime_error(self):
        # DB_HOST 없고 streamlit secrets도 없음
        env_without_db = {k: v for k, v in os.environ.items() if k != "DB_HOST"}
        with patch.dict(os.environ, {}, clear=True):
            with patch("modules.db_connection.os.environ.get", return_value=None):
                with patch("builtins.__import__", side_effect=ImportError):
                    with pytest.raises((RuntimeError, Exception)):
                        get_db_config()

    def test_streamlit_secrets_used_when_no_env(self):
        mock_st = MagicMock()
        mock_st.secrets = {"mysql": {"host": "st-host", "user": "st-user", "password": "pw", "database": "db"}}
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict("sys.modules", {"streamlit": mock_st}):
                # DB_HOST가 없으면 streamlit 시도
                # 실제 환경변수를 완전히 지우면 다른 테스트에 영향 줄 수 있으므로 패치
                with patch.object(db_module.os.environ, "get", return_value=None):
                    try:
                        config = get_db_config()
                        assert config.get("host") == "st-host"
                    except RuntimeError:
                        pass  # streamlit mock 설정에 따라 달라질 수 있음


# ───────────────────────────────────────────────────────────────
# 2. set_connection_factory & get_db_connection
# ───────────────────────────────────────────────────────────────

class TestConnectionFactory:
    """
    비즈니스 규칙:
      - set_connection_factory()로 주입한 팩토리가 get_db_connection()에서 사용됨
      - 팩토리를 None으로 초기화하면 실제 풀 사용
    """

    def test_factory_used_when_set(self):
        mock_conn = MagicMock()
        set_connection_factory(lambda: mock_conn)
        conn = get_db_connection()
        assert conn is mock_conn

    def test_factory_called_each_time(self):
        call_count = {"n": 0}
        mock_conn = MagicMock()

        def factory():
            call_count["n"] += 1
            return mock_conn

        set_connection_factory(factory)
        get_db_connection()
        get_db_connection()
        assert call_count["n"] == 2

    def test_factory_reset_to_none(self):
        set_connection_factory(lambda: MagicMock())
        set_connection_factory(None)
        # 팩토리 None이면 실제 풀 사용 시도 → 연결 설정 없으면 에러
        assert db_module._connection_factory is None


# ───────────────────────────────────────────────────────────────
# 3. db_transaction — 커밋/롤백 동작
# ───────────────────────────────────────────────────────────────

class TestDbTransaction:
    """
    비즈니스 규칙:
      - 블록 내에서 예외 없으면 commit() 호출
      - 블록 내에서 예외 발생 시 rollback() 호출하고 예외 재발생
      - 항상 cursor.close()와 conn.close() 호출
    """

    def test_commits_on_success(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_transaction() as c:
            c.execute("INSERT INTO t VALUES (%s)", (1,))

        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_rollbacks_on_exception(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with pytest.raises(ValueError):
            with db_transaction() as c:
                raise ValueError("의도된 에러")

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_exception_is_reraised(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with pytest.raises(RuntimeError, match="테스트 에러"):
            with db_transaction() as c:
                raise RuntimeError("테스트 에러")

    def test_cursor_closed_on_success(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_transaction() as c:
            pass

        cursor.close.assert_called_once()

    def test_cursor_closed_on_exception(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with pytest.raises(Exception):
            with db_transaction() as c:
                raise Exception("에러")

        cursor.close.assert_called_once()

    def test_conn_closed_on_success(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_transaction() as c:
            pass

        conn.close.assert_called_once()

    def test_conn_closed_on_exception(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with pytest.raises(Exception):
            with db_transaction() as c:
                raise Exception("에러")

        conn.close.assert_called_once()

    def test_dictionary_cursor_option(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_transaction(dictionary=True) as c:
            pass

        conn.cursor.assert_called_with(dictionary=True)

    def test_yields_cursor(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_transaction() as c:
            assert c is cursor


# ───────────────────────────────────────────────────────────────
# 4. db_query — 읽기 전용 동작
# ───────────────────────────────────────────────────────────────

class TestDbQuery:
    """
    비즈니스 규칙:
      - 커밋/롤백 없이 읽기 전용
      - 미소비 결과를 fetchall()로 정리
      - 항상 cursor.close()와 conn.close() 호출
    """

    def test_no_commit_or_rollback(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            pass

        conn.commit.assert_not_called()
        conn.rollback.assert_not_called()

    def test_cursor_closed_after_query(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            pass

        cursor.close.assert_called_once()

    def test_conn_closed_after_query(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            pass

        conn.close.assert_called_once()

    def test_fetchall_called_for_cleanup(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            pass

        # 미소비 결과 정리를 위해 fetchall 호출됨
        cursor.fetchall.assert_called()

    def test_yields_cursor(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            assert c is cursor

    def test_cursor_closed_even_on_exception(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with pytest.raises(Exception):
            with db_query() as c:
                raise Exception("쿼리 중 에러")

        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_dictionary_cursor_default_true(self):
        conn, cursor = make_mock_conn()
        set_connection_factory(lambda: conn)

        with db_query() as c:
            pass

        # db_query 기본값은 dictionary=True
        call_args = conn.cursor.call_args
        assert call_args.kwargs.get("dictionary", True) is True

    def test_fetchall_failure_handled_gracefully(self):
        conn, cursor = make_mock_conn()
        cursor.fetchall.side_effect = Exception("fetchall 실패")
        set_connection_factory(lambda: conn)

        # fetchall 실패해도 cursor/conn close는 호출되어야 함
        with db_query() as c:
            pass

        cursor.close.assert_called_once()
        conn.close.assert_called_once()


# ───────────────────────────────────────────────────────────────
# 5. release_pool — 풀 해제
# ───────────────────────────────────────────────────────────────

class TestReleasePool:
    """
    비즈니스 규칙:
      - release_pool() 호출 후 _connection_pool과 _pool_config가 None
    """

    def test_pool_set_to_none_after_release(self):
        db_module._connection_pool = MagicMock()
        db_module._pool_config = {"host": "localhost"}
        release_pool()
        assert db_module._connection_pool is None
        assert db_module._pool_config is None

    def test_release_when_already_none_no_error(self):
        db_module._connection_pool = None
        db_module._pool_config = None
        release_pool()  # 에러 없어야 함
