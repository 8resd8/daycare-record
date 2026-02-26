from typing import List, Optional, Dict, Any
from .base import BaseRepository


class UserRepository(BaseRepository):
    """Repository for user (employee) CRUD operations."""

    def list_users(self, keyword: str = None, work_status: str = None) -> List[Dict[str, Any]]:
        query = """
            SELECT
                user_id,
                name,
                gender,
                birth_date,
                work_status,
                job_type,
                hire_date,
                resignation_date,
                license_name,
                license_date,
                created_at
            FROM users
            WHERE 1=1
        """
        params = []

        if keyword:
            like = f"%{keyword}%"
            query += " AND (name LIKE %s OR job_type LIKE %s)"
            params.extend([like, like])

        if work_status and work_status != "전체":
            query += " AND work_status = %s"
            params.append(work_status)

        query += " ORDER BY name"
        return self._execute_query(query, tuple(params))

    def create_user(
        self,
        username: str,
        password: str,
        name: str,
        gender: Optional[str] = None,
        birth_date=None,
        work_status: str = "재직",
        job_type: Optional[str] = None,
        hire_date=None,
        resignation_date=None,
        license_name: Optional[str] = None,
        license_date=None,
        role: str = "EMPLOYEE",
    ) -> int:
        query = """
            INSERT INTO users (
                username, password, role, name, gender, birth_date,
                work_status, job_type, hire_date, resignation_date,
                license_name, license_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_transaction_lastrowid(
            query,
            (
                username,
                password,
                role,
                name,
                gender,
                birth_date,
                work_status,
                job_type,
                hire_date,
                resignation_date,
                license_name,
                license_date,
            ),
        )

    def update_user(
        self,
        user_id: int,
        name: str,
        gender: Optional[str] = None,
        birth_date=None,
        work_status: str = "재직",
        job_type: Optional[str] = None,
        hire_date=None,
        resignation_date=None,
        license_name: Optional[str] = None,
        license_date=None,
    ) -> int:
        query = """
            UPDATE users SET
                name = %s,
                gender = %s,
                birth_date = %s,
                work_status = %s,
                job_type = %s,
                hire_date = %s,
                resignation_date = %s,
                license_name = %s,
                license_date = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        return self._execute_transaction(
            query,
            (
                name,
                gender,
                birth_date,
                work_status,
                job_type,
                hire_date,
                resignation_date,
                license_name,
                license_date,
                user_id,
            ),
        )

    def soft_delete_user(self, user_id: int) -> int:
        """퇴사 처리 (실제 삭제 대신 상태 변경)."""
        query = """
            UPDATE users SET
                work_status = '퇴사',
                resignation_date = CURDATE(),
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        return self._execute_transaction(query, (user_id,))

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                user_id, name, gender, birth_date, work_status,
                job_type, hire_date, resignation_date, license_name, license_date,
                created_at
            FROM users
            WHERE user_id = %s
        """
        return self._execute_query_one(query, (user_id,))
