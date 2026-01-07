from typing import Dict, List, Optional, Any
from modules.db_connection import db_query, db_transaction


class BaseRepository:
    """Base repository class with common database operations."""
    
    def __init__(self):
        pass
    
    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a read-only query and return results."""
        with db_query() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    
    def _execute_query_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a read-only query and return single result."""
        with db_query() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()
    
    def _execute_transaction(self, query: str, params: tuple = None) -> int:
        """Execute a write query in a transaction and return affected rows."""
        with db_transaction() as cursor:
            cursor.execute(query, params or ())
            return cursor.rowcount
    
    def _execute_transaction_lastrowid(self, query: str, params: tuple = None) -> int:
        """Execute an insert query in a transaction and return last row ID."""
        with db_transaction() as cursor:
            cursor.execute(query, params or ())
            return cursor.lastrowid
    
    def _execute_transaction_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute multiple write queries in a transaction."""
        with db_transaction() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
