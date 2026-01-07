from typing import Optional
from .base import BaseRepository


class WeeklyStatusRepository(BaseRepository):
    """Repository for weekly status report operations."""
    
    def save_weekly_status(self, customer_id: int, start_date, end_date, 
                          report_text: str) -> None:
        """Save or update weekly status report."""
        query = """
            INSERT INTO weekly_status (customer_id, start_date, end_date, report_text)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                report_text=VALUES(report_text),
                updated_at=CURRENT_TIMESTAMP
        """
        self._execute_transaction(query, (customer_id, start_date, end_date, report_text))
    
    def load_weekly_status(self, customer_id: int, start_date, end_date) -> Optional[str]:
        """Load weekly status report for a specific period."""
        query = """
            SELECT report_text
            FROM weekly_status
            WHERE customer_id=%s AND start_date=%s AND end_date=%s
        """
        result = self._execute_query_one(query, (customer_id, start_date, end_date))
        return result['report_text'] if result else None
    
    def get_all_by_customer(self, customer_id: int, limit: int = 10) -> list:
        """Get all weekly status reports for a customer."""
        query = """
            SELECT start_date, end_date, report_text, created_at, updated_at
            FROM weekly_status
            WHERE customer_id = %s
            ORDER BY start_date DESC
            LIMIT %s
        """
        return self._execute_query(query, (customer_id, limit))
    
    def delete_weekly_status(self, customer_id: int, start_date, end_date) -> int:
        """Delete a weekly status report."""
        query = """
            DELETE FROM weekly_status
            WHERE customer_id=%s AND start_date=%s AND end_date=%s
        """
        return self._execute_transaction(query, (customer_id, start_date, end_date))
