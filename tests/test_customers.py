"""
customers.py 단위 테스트
=========================
비즈니스 규칙:
  - resolve_customer_id: 인정번호 → 이름+생년월일 → 이름 순으로 조회
  - CRUD 함수는 CustomerRepository에 위임
"""

import pytest
from unittest.mock import MagicMock, patch


# ───────────────────────────────────────────────────────────────
# resolve_customer_id 테스트
# ───────────────────────────────────────────────────────────────

class TestResolveCustomerId:
    """
    비즈니스 규칙 (우선순위):
      1. recognition_no(인정번호)로 조회
      2. name + birth_date로 조회
      3. name만으로 조회 (최신 순 첫 번째)
      4. 모두 실패하면 None 반환
    """

    def _make_mock_repo(self, by_recog=None, by_name_birth=None, by_name=None):
        repo = MagicMock()
        repo.find_by_recognition_no.return_value = by_recog
        repo.find_by_name_and_birth.return_value = by_name_birth
        repo.find_by_name.return_value = by_name
        return repo

    def test_resolves_by_recognition_no_first(self):
        repo = self._make_mock_repo(
            by_recog={"customer_id": 10},
            by_name_birth={"customer_id": 20},
        )
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="홍길동", recognition_no="L001", birth_date="1950-01-01")
        assert result == 10
        repo.find_by_recognition_no.assert_called_once_with("L001")

    def test_falls_back_to_name_and_birth(self):
        repo = self._make_mock_repo(
            by_recog=None,
            by_name_birth={"customer_id": 20},
        )
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="홍길동", recognition_no="L001", birth_date="1950-01-01")
        assert result == 20
        repo.find_by_name_and_birth.assert_called_once_with("홍길동", "1950-01-01")

    def test_falls_back_to_name_only(self):
        repo = self._make_mock_repo(
            by_recog=None,
            by_name_birth=None,
            by_name={"customer_id": 30},
        )
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="홍길동", recognition_no=None, birth_date=None)
        assert result == 30
        repo.find_by_name.assert_called_once_with("홍길동")

    def test_returns_none_when_all_fail(self):
        repo = self._make_mock_repo(by_recog=None, by_name_birth=None, by_name=None)
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="없는사람", recognition_no=None, birth_date=None)
        assert result is None

    def test_skips_recognition_no_when_not_provided(self):
        repo = self._make_mock_repo(by_name={"customer_id": 5})
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="홍길동")
        repo.find_by_recognition_no.assert_not_called()
        assert result == 5

    def test_skips_name_birth_when_no_birth_date(self):
        repo = self._make_mock_repo(by_name={"customer_id": 5})
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name="홍길동", birth_date=None)
        repo.find_by_name_and_birth.assert_not_called()

    def test_skips_name_birth_when_no_name(self):
        repo = self._make_mock_repo()
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import resolve_customer_id
            result = resolve_customer_id(name=None, birth_date="1950-01-01")
        repo.find_by_name_and_birth.assert_not_called()


# ───────────────────────────────────────────────────────────────
# CRUD 위임 테스트
# ───────────────────────────────────────────────────────────────

class TestCustomerCrudDelegation:
    """
    비즈니스 규칙:
      - 각 함수는 CustomerRepository 메서드에 인자를 그대로 전달
    """

    def test_list_customers_delegates_to_repo(self):
        repo = MagicMock()
        repo.list_customers.return_value = [{"customer_id": 1}]
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import list_customers
            result = list_customers(keyword="홍")
        repo.list_customers.assert_called_once_with("홍")
        assert result == [{"customer_id": 1}]

    def test_list_customers_no_keyword(self):
        repo = MagicMock()
        repo.list_customers.return_value = []
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import list_customers
            list_customers()
        repo.list_customers.assert_called_once_with(None)

    def test_get_customer_delegates_to_repo(self):
        repo = MagicMock()
        repo.get_customer.return_value = {"customer_id": 1, "name": "홍길동"}
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import get_customer
            result = get_customer(1)
        repo.get_customer.assert_called_once_with(1)
        assert result["name"] == "홍길동"

    def test_create_customer_delegates_all_args(self):
        repo = MagicMock()
        repo.create_customer.return_value = 99
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import create_customer
            result = create_customer(
                name="홍길동", birth_date="1950-01-01",
                gender="M", recognition_no="L001",
                benefit_start_date="2024-01-01", grade="3등급"
            )
        repo.create_customer.assert_called_once_with(
            name="홍길동", birth_date="1950-01-01",
            gender="M", recognition_no="L001",
            benefit_start_date="2024-01-01", grade="3등급"
        )
        assert result == 99

    def test_update_customer_delegates_all_args(self):
        repo = MagicMock()
        repo.update_customer.return_value = 1
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import update_customer
            result = update_customer(
                customer_id=1, name="홍길동", birth_date="1950-01-01",
                gender="M", recognition_no="L001",
                benefit_start_date="2024-01-01", grade="3등급"
            )
        assert result == 1

    def test_delete_customer_delegates_to_repo(self):
        repo = MagicMock()
        repo.delete_customer.return_value = 1
        with patch("modules.customers.customer_repo", repo):
            from modules.customers import delete_customer
            result = delete_customer(1)
        repo.delete_customer.assert_called_once_with(1)
        assert result == 1
