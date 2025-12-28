"""Customer business logic module."""

from typing import List, Optional, Dict
from modules.repositories import CustomerRepository


# 리포지토리 초기화
customer_repo = CustomerRepository()


def list_customers(keyword: str = None) -> List[Dict]:
    """List all customers or search by keyword."""
    return customer_repo.list_customers(keyword)


def get_customer(customer_id: int) -> Optional[Dict]:
    """Get a single customer by ID."""
    return customer_repo.get_customer(customer_id)


def create_customer(*, name: str, birth_date, gender: str = None, 
                   recognition_no: str = None, benefit_start_date = None, 
                   grade: str = None) -> int:
    """Create a new customer and return the ID."""
    return customer_repo.create_customer(
        name=name,
        birth_date=birth_date,
        gender=gender,
        recognition_no=recognition_no,
        benefit_start_date=benefit_start_date,
        grade=grade
    )


def update_customer(*, customer_id: int, name: str, birth_date, 
                   gender: str = None, recognition_no: str = None, 
                   benefit_start_date = None, grade: str = None) -> int:
    """Update a customer and return the number of affected rows."""
    return customer_repo.update_customer(
        customer_id=customer_id,
        name=name,
        birth_date=birth_date,
        gender=gender,
        recognition_no=recognition_no,
        benefit_start_date=benefit_start_date,
        grade=grade
    )


def delete_customer(customer_id: int) -> int:
    """Delete a customer and return the number of affected rows."""
    return customer_repo.delete_customer(customer_id)


def resolve_customer_id(*, name: str, recognition_no: str = None, birth_date=None) -> Optional[int]:
    """Resolve customer_id for weekly_status storage.

    Priority:
    1) recognition_no (unique-ish)
    2) name + birth_date
    3) name (fallback, newest)
    """
    if recognition_no:
        customer = customer_repo.find_by_recognition_no(recognition_no)
        if customer:
            return customer['customer_id']
    
    if name and birth_date:
        customer = customer_repo.find_by_name_and_birth(name, birth_date)
        if customer:
            return customer['customer_id']
    
    if name:
        customer = customer_repo.find_by_name(name)
        if customer:
            return customer['customer_id']
    
    return None
