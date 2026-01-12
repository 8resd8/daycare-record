"""데이터베이스 연결 유틸리티 및 컨텍스트 매니저

이 모듈은 다음을 지원하는 데이터베이스 연결 관리 기능을 제공합니다:
- Streamlit secrets (프로덕션용)
- 환경변수 (테스트/CLI용)
- 의존성 주입 (단위 테스트용)
- 연결 풀링 (성능 최적화)
"""

import os
import gc
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from typing import Iterator, Optional, Callable, Dict, Any

# Connection factory for dependency injection (테스트용)
_connection_factory: Optional[Callable[[], Any]] = None

# Connection pool (성능 최적화)
_connection_pool: Optional[pooling.MySQLConnectionPool] = None
_pool_config: Optional[Dict[str, Any]] = None


def set_connection_factory(factory: Optional[Callable[[], Any]]) -> None:
    """테스트용 커스텀 연결 팩토리 설정
    
    Args:
        factory: 연결과 유사한 객체를 반환하는 호출 가능한 객체, 또는 초기화를 위해 None
    """
    global _connection_factory
    _connection_factory = factory


def get_db_config() -> Dict[str, Any]:
    """사용 가능한 소스에서 데이터베이스 설정 가져오기
    
    우선순위:
    1. 환경변수 (테스트/CLI용)
    2. Streamlit secrets (프로덕션용)
    
    Returns:
        데이터베이스 설정 딕셔너리
    """
    # 환경변수에서 설정 확인
    if os.environ.get('DB_HOST'):
        return {
            'host': os.environ.get('DB_HOST'),
            'port': int(os.environ.get('DB_PORT', 3306)),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'database': os.environ.get('DB_NAME'),
        }
    
    # Streamlit secrets에서 설정 확인
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'mysql' in st.secrets:
            return dict(st.secrets["mysql"])
    except (ImportError, RuntimeError):
        pass
    
    raise RuntimeError("Database configuration not found. Set environment variables or Streamlit secrets.")


def _get_connection_pool() -> pooling.MySQLConnectionPool:
    """연결 풀 가져오기
    """
    global _connection_pool, _pool_config
    
    config = get_db_config()
    
    # 설정이 변경되었거나 풀이 없으면 새로 생성
    if _connection_pool is None or _pool_config != config:
        if _connection_pool is not None:
            # 기존 풀 정리
            try:
                _connection_pool = None
                gc.collect()
            except:
                pass
        
        _pool_config = config.copy()
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name="arisa_pool",
            pool_size=5,
            pool_reset_session=True,
            **config
        )
    
    return _connection_pool


def get_db_connection():
    """데이터베이스 연결 가져오기
    
    설정된 커스텀 팩토리가 있으면 사용하고(테스트용),
    그렇지 않으면 연결 풀에서 연결을 가져옵니다.
    """
    if _connection_factory is not None:
        return _connection_factory()
    
    try:
        pool = _get_connection_pool()
        return pool.get_connection()
    except Exception:
        # 풀링 실패 시 직접 연결 (폴백)
        config = get_db_config()
        return mysql.connector.connect(**config)


@contextmanager
def db_transaction(dictionary: bool = False) -> Iterator[mysql.connector.cursor.MySQLCursor]:
    """자동 커밋/롤백이 포함된 데이터베이스 트랜잭션 컨텍스트 매니저
    
    Args:
        dictionary: 딕셔너리 커서 반환 여부 (기본값: False)
        
    Yields:
        MySQL 커서 객체
        
    Usage:
        with db_transaction() as cursor:
            cursor.execute("INSERT INTO table VALUES (%s)", (value,))
            # 성공 시 자동 커밋, 예외 발생 시 롤백
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@contextmanager
def db_query(dictionary: bool = True) -> Iterator[mysql.connector.cursor.MySQLCursor]:
    """읽기 전용 데이터베이스 쿼리용 컨텍스트 매니저
    
    Args:
        dictionary: 딕셔너리 커서 반환 여부 (기본값: True)
        
    Yields:
        MySQL 커서 객체
        
    Usage:
        with db_query() as cursor:
            cursor.execute("SELECT * FROM table WHERE id = %s", (id,))
            results = cursor.fetchall()
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=dictionary, buffered=False)  # 메모리 최적화: unbuffered
    try:
        yield cursor
    finally:
        # 미소비 결과 정리
        try:
            cursor.fetchall()
        except:
            pass
        cursor.close()
        conn.close()


def release_pool():
    """연결 풀 해제 (메모리 정리용)"""
    global _connection_pool, _pool_config
    _connection_pool = None
    _pool_config = None
    gc.collect()
