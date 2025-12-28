"""Customer repository for database operations."""

from typing import List, Optional, Dict
from .base import BaseRepository


class CustomerRepository(BaseRepository):
    """Repository for customer-related database operations."""
    
    def list_customers(self, keyword: str = None) -> List[Dict]:
        """List all customers or search by keyword."""
        if keyword:
            like = f"%{keyword}%"
            query = """
                SELECT customer_id, name, birth_date, gender, recognition_no, 
                       benefit_start_date, grade
                FROM customers
                WHERE name LIKE %s OR recognition_no LIKE %s
                ORDER BY customer_id DESC
            """
            return self._execute_query(query, (like, like))
        else:
            query = """
                SELECT customer_id, name, birth_date, gender, recognition_no, 
                       benefit_start_date, grade
                FROM customers
                ORDER BY customer_id DESC
            """
            return self._execute_query(query)
    
    def get_customer(self, customer_id: int) -> Optional[Dict]:
        """Get a single customer by ID."""
        query = """
            SELECT customer_id, name, birth_date, gender, recognition_no, 
                   benefit_start_date, grade
            FROM customers
            WHERE customer_id = %s
        """
        return self._execute_query_one(query, (customer_id,))
    
    def create_customer(self, name: str, birth_date, gender: str = None, 
                       recognition_no: str = None, benefit_start_date = None, 
                       grade: str = None) -> int:
        """Create a new customer and return the ID."""
        query = """
            INSERT INTO customers (name, birth_date, gender, recognition_no, 
                                  benefit_start_date, grade)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._execute_transaction_lastrowid(
            query, (name, birth_date, gender, recognition_no, 
                   benefit_start_date, grade)
        )
    
    def update_customer(self, customer_id: int, name: str, birth_date, 
                       gender: str = None, recognition_no: str = None, 
                       benefit_start_date = None, grade: str = None) -> int:
        """Update a customer and return the number of affected rows."""
        query = """
            UPDATE customers
            SET name=%s, birth_date=%s, gender=%s, recognition_no=%s,
                benefit_start_date=%s, grade=%s
            WHERE customer_id=%s
        """
        return self._execute_transaction(
            query, (name, birth_date, gender, recognition_no, 
                   benefit_start_date, grade, customer_id)
        )
    
    def delete_customer(self, customer_id: int) -> int:
        """Delete a customer and return the number of affected rows."""
        query = "DELETE FROM customers WHERE customer_id=%s"
        return self._execute_transaction(query, (customer_id,))
    
    def find_by_name(self, name: str) -> Optional[Dict]:
        """Find a customer by name (returns the most recent one)."""
        query = """
            SELECT customer_id, name, birth_date, gender, recognition_no,
                   benefit_start_date, grade
            FROM customers
            WHERE name = %s
            ORDER BY customer_id DESC
            LIMIT 1
        """
        return self._execute_query_one(query, (name,))
    
    def find_by_recognition_no(self, recognition_no: str) -> Optional[Dict]:
        """Find a customer by recognition number (returns the most recent one)."""
        query = """
            SELECT customer_id, name, birth_date, gender, recognition_no,
                   benefit_start_date, grade
            FROM customers
            WHERE recognition_no = %s
            ORDER BY customer_id DESC
            LIMIT 1
        """
        return self._execute_query_one(query, (recognition_no,))
    
    def find_by_name_and_birth(self, name: str, birth_date) -> Optional[Dict]:
        """Find a customer by name and birth date (returns the most recent one)."""
        query = """
            SELECT customer_id, name, birth_date, gender, recognition_no,
                   benefit_start_date, grade
            FROM customers
            WHERE name = %s AND birth_date = %s
            ORDER BY customer_id DESC
            LIMIT 1
        """
        return self._execute_query_one(query, (name, birth_date))
    
    def get_or_create(self, name: str, birth_date = None, grade: str = None,
                     recognition_no: str = None, facility_name: str = None,
                     facility_code: str = None) -> int:
        """Get existing customer or create a new one."""
        # 먼저 기존 고객 찾기
        existing = self.find_by_name(name)
        
        if existing:
            customer_id = existing['customer_id']
            # 새 정보가 제공되면 업데이트
            self.update_customer(
                customer_id=customer_id,
                name=name,
                birth_date=birth_date,
                grade=grade,
                recognition_no=recognition_no
            )
            return customer_id
        else:
            # 새 고객 생성
            return self.create_customer(
                name=name,
                birth_date=birth_date,
                grade=grade,
                recognition_no=recognition_no
            )
