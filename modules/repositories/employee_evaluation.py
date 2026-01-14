from typing import Dict, List, Optional
from datetime import date
from .base import BaseRepository


class EmployeeEvaluationRepository(BaseRepository):
    """Repository for employee evaluation operations."""
    
    def save_evaluation(
        self,
        record_id: int,
        target_user_id: int,
        category: str,
        evaluation_type: str,
        evaluation_date: date,
        target_date: date = None,
        evaluator_user_id: int = None,
        score: int = 1,
        comment: str = None
    ) -> int:
        """Save employee evaluation and return the inserted ID."""
        insert_query = '''
            INSERT INTO employee_evaluations (
                record_id, target_date, target_user_id, evaluator_user_id,
                category, evaluation_type, score, comment, evaluation_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        return self._execute_transaction_lastrowid(
            insert_query, (
                record_id, target_date, target_user_id, evaluator_user_id,
                category, evaluation_type, score, comment, evaluation_date
            )
        )
    
    def get_evaluations_by_record(self, record_id: int) -> List[Dict]:
        """Get all employee evaluations for a specific record."""
        query = """
            SELECT 
                ee.emp_eval_id, ee.record_id, ee.target_date, ee.category, ee.evaluation_type,
                ee.score, ee.comment, ee.evaluation_date,
                tu.name AS target_user_name,
                eu.name AS evaluator_user_name
            FROM employee_evaluations ee
            LEFT JOIN users tu ON ee.target_user_id = tu.user_id
            LEFT JOIN users eu ON ee.evaluator_user_id = eu.user_id
            WHERE ee.record_id = %s
            ORDER BY ee.created_at DESC
        """
        return self._execute_query(query, (record_id,))
    
    def get_user_id_by_name(self, name: str) -> Optional[int]:
        """Get user ID by name."""
        query = "SELECT user_id FROM users WHERE name = %s LIMIT 1"
        result = self._execute_query_one(query, (name,))
        return result['user_id'] if result else None
    
    def get_all_users(self) -> List[Dict]:
        """Get all users for dropdown selection."""
        query = "SELECT user_id, name FROM users ORDER BY name"
        return self._execute_query(query, ())
    
    def delete_evaluation(self, emp_eval_id: int) -> int:
        """Delete an employee evaluation by ID."""
        query = "DELETE FROM employee_evaluations WHERE emp_eval_id = %s"
        return self._execute_transaction(query, (emp_eval_id,))
    
    def find_existing_evaluation(
        self,
        record_id: int,
        target_user_id: int,
        category: str,
        evaluation_type: str
    ) -> Optional[int]:
        """Find existing evaluation ID for the same record, target, category, and type."""
        query = """
            SELECT emp_eval_id FROM employee_evaluations
            WHERE record_id = %s AND target_user_id = %s 
              AND category = %s AND evaluation_type = %s
            LIMIT 1
        """
        result = self._execute_query_one(query, (record_id, target_user_id, category, evaluation_type))
        return result['emp_eval_id'] if result else None
    
    def update_evaluation(
        self,
        emp_eval_id: int,
        evaluation_date: date,
        target_date: date = None,
        evaluator_user_id: int = None,
        score: int = 1,
        comment: str = None
    ) -> int:
        """Update an existing employee evaluation."""
        update_query = '''
            UPDATE employee_evaluations SET
                target_date = %s,
                evaluator_user_id = %s,
                score = %s,
                comment = %s,
                evaluation_date = %s
            WHERE emp_eval_id = %s
        '''
        return self._execute_transaction(
            update_query, (target_date, evaluator_user_id, score, comment, evaluation_date, emp_eval_id)
        )
