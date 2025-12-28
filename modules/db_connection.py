"""Database connection utilities and context managers."""

import mysql.connector
import streamlit as st
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def db_transaction(dictionary: bool = False) -> Iterator[mysql.connector.cursor.MySQLCursor]:
    """Context manager for database transactions with automatic commit/rollback.
    
    Args:
        dictionary: Whether to return a dictionary cursor (default: False)
        
    Yields:
        MySQL cursor object
        
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
    """Context manager for read-only database queries.
    
    Args:
        dictionary: Whether to return a dictionary cursor (default: True)
        
    Yields:
        MySQL cursor object
        
    Usage:
        with db_query() as cursor:
            cursor.execute("SELECT * FROM table WHERE id = %s", (id,))
            results = cursor.fetchall()
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def get_db_connection():
    """Get a database connection using Streamlit secrets."""
    return mysql.connector.connect(**st.secrets["mysql"])
