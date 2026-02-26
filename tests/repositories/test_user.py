"""UserRepository 테스트

직원(사용자) CRUD 데이터 액세스 레이어 테스트.
향후 백엔드 API(/api/users)로 분리 시 동일한 비즈니스 규칙이 적용됩니다.
"""

import pytest
from unittest.mock import patch
from datetime import date
from modules.repositories.user import UserRepository


class TestUserRepository:
    """UserRepository 테스트 클래스"""

    @pytest.fixture
    def repo(self):
        return UserRepository()

    @pytest.fixture
    def mock_execute_query(self):
        with patch.object(UserRepository, '_execute_query') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_query_one(self):
        with patch.object(UserRepository, '_execute_query_one') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_transaction(self):
        with patch.object(UserRepository, '_execute_transaction') as mock:
            yield mock

    @pytest.fixture
    def mock_execute_transaction_lastrowid(self):
        with patch.object(UserRepository, '_execute_transaction_lastrowid') as mock:
            yield mock

    @pytest.fixture
    def sample_user(self):
        return {
            'user_id': 1,
            'name': '홍길동',
            'gender': 'M',
            'birth_date': '1985-03-15',
            'work_status': '재직',
            'job_type': '요양보호사',
            'hire_date': '2022-01-01',
            'resignation_date': None,
            'license_name': '요양보호사 1급',
            'license_date': '2021-12-01',
            'created_at': '2022-01-01 09:00:00'
        }

    # ========== list_users 테스트 ==========

    def test_list_users_all(self, repo, mock_execute_query, sample_user):
        """전체 직원 목록 조회"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users()

        assert len(result) == 1
        assert result[0]['name'] == '홍길동'
        mock_execute_query.assert_called_once()

    def test_list_users_with_keyword(self, repo, mock_execute_query, sample_user):
        """이름 키워드로 직원 검색"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users(keyword='홍')

        mock_execute_query.assert_called_once()
        call_args = mock_execute_query.call_args[0]
        # LIKE 파라미터 확인
        assert '%홍%' in call_args[1]

    def test_list_users_with_job_type_keyword(self, repo, mock_execute_query, sample_user):
        """직종 키워드로 직원 검색"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users(keyword='요양보호사')

        call_args = mock_execute_query.call_args[0]
        assert '%요양보호사%' in call_args[1]

    def test_list_users_filter_by_work_status(self, repo, mock_execute_query, sample_user):
        """재직 상태로 필터링"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users(work_status='재직')

        call_args = mock_execute_query.call_args[0]
        assert '재직' in call_args[1]

    def test_list_users_work_status_all_ignored(self, repo, mock_execute_query, sample_user):
        """'전체' 상태는 필터 미적용"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users(work_status='전체')

        call_args = mock_execute_query.call_args[0]
        # '전체' 자체가 SQL 파라미터에 포함되지 않아야 함
        assert '전체' not in str(call_args[1])

    def test_list_users_empty_result(self, repo, mock_execute_query):
        """직원이 없는 경우 빈 리스트 반환"""
        mock_execute_query.return_value = []

        result = repo.list_users()

        assert result == []

    def test_list_users_combined_filter(self, repo, mock_execute_query, sample_user):
        """키워드 + 재직상태 복합 필터"""
        mock_execute_query.return_value = [sample_user]

        result = repo.list_users(keyword='홍', work_status='재직')

        call_args = mock_execute_query.call_args[0]
        assert '%홍%' in call_args[1]
        assert '재직' in call_args[1]

    # ========== create_user 테스트 ==========

    def test_create_user_success(self, repo, mock_execute_transaction_lastrowid):
        """직원 생성 성공 - 새 user_id 반환"""
        mock_execute_transaction_lastrowid.return_value = 5

        result = repo.create_user(
            username='hong123',
            password='hashed_password',
            name='홍길동',
            gender='M',
            birth_date=date(1985, 3, 15),
            work_status='재직',
            job_type='요양보호사',
            hire_date=date(2022, 1, 1)
        )

        assert result == 5
        mock_execute_transaction_lastrowid.assert_called_once()

    def test_create_user_minimal_fields(self, repo, mock_execute_transaction_lastrowid):
        """최소 필드만으로 직원 생성"""
        mock_execute_transaction_lastrowid.return_value = 3

        result = repo.create_user(
            username='min_user',
            password='pass',
            name='최소직원'
        )

        assert result == 3

    def test_create_user_with_role(self, repo, mock_execute_transaction_lastrowid):
        """관리자 역할로 직원 생성"""
        mock_execute_transaction_lastrowid.return_value = 1

        result = repo.create_user(
            username='admin',
            password='admin_pass',
            name='관리자',
            role='ADMIN'
        )

        assert result == 1
        call_args = mock_execute_transaction_lastrowid.call_args[0][1]
        assert 'ADMIN' in call_args

    def test_create_user_default_role_is_employee(self, repo, mock_execute_transaction_lastrowid):
        """기본 역할이 EMPLOYEE인지 확인"""
        mock_execute_transaction_lastrowid.return_value = 2

        repo.create_user(username='emp', password='pass', name='직원')

        call_args = mock_execute_transaction_lastrowid.call_args[0][1]
        assert 'EMPLOYEE' in call_args

    def test_create_user_query_contains_insert(self, repo, mock_execute_transaction_lastrowid):
        """INSERT 쿼리가 실행되는지 확인"""
        mock_execute_transaction_lastrowid.return_value = 1

        repo.create_user(username='u', password='p', name='테스트')

        query = mock_execute_transaction_lastrowid.call_args[0][0]
        assert 'INSERT' in query.upper()
        assert 'users' in query.lower()

    # ========== update_user 테스트 ==========

    def test_update_user_success(self, repo, mock_execute_transaction):
        """직원 정보 수정 성공"""
        mock_execute_transaction.return_value = 1

        result = repo.update_user(
            user_id=1,
            name='홍길동',
            gender='M',
            work_status='재직',
            job_type='사회복지사'
        )

        assert result == 1
        mock_execute_transaction.assert_called_once()

    def test_update_user_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 직원 수정 시 0 반환"""
        mock_execute_transaction.return_value = 0

        result = repo.update_user(
            user_id=999,
            name='없는직원'
        )

        assert result == 0

    def test_update_user_query_contains_update(self, repo, mock_execute_transaction):
        """UPDATE 쿼리가 실행되는지 확인"""
        mock_execute_transaction.return_value = 1

        repo.update_user(user_id=1, name='홍길동')

        query = mock_execute_transaction.call_args[0][0]
        assert 'UPDATE' in query.upper()
        assert 'users' in query.lower()

    def test_update_user_includes_user_id_in_params(self, repo, mock_execute_transaction):
        """UPDATE 쿼리 파라미터에 user_id가 포함되는지 확인"""
        mock_execute_transaction.return_value = 1

        repo.update_user(user_id=7, name='홍길동')

        params = mock_execute_transaction.call_args[0][1]
        assert 7 in params

    # ========== soft_delete_user 테스트 ==========

    def test_soft_delete_user_success(self, repo, mock_execute_transaction):
        """퇴사 처리 성공 (soft delete)"""
        mock_execute_transaction.return_value = 1

        result = repo.soft_delete_user(user_id=1)

        assert result == 1

    def test_soft_delete_user_changes_status_not_deletes(self, repo, mock_execute_transaction):
        """soft_delete는 레코드를 삭제하지 않고 상태를 변경한다"""
        mock_execute_transaction.return_value = 1

        repo.soft_delete_user(user_id=1)

        query = mock_execute_transaction.call_args[0][0]
        # DELETE가 아닌 UPDATE 쿼리여야 함
        assert 'UPDATE' in query.upper()
        assert 'DELETE' not in query.upper()
        assert '퇴사' in query

    def test_soft_delete_user_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 직원 퇴사 처리"""
        mock_execute_transaction.return_value = 0

        result = repo.soft_delete_user(user_id=999)

        assert result == 0

    # ========== get_user 테스트 ==========

    def test_get_user_exists(self, repo, mock_execute_query_one, sample_user):
        """존재하는 직원 조회"""
        mock_execute_query_one.return_value = sample_user

        result = repo.get_user(1)

        assert result is not None
        assert result['user_id'] == 1
        assert result['name'] == '홍길동'

    def test_get_user_not_exists(self, repo, mock_execute_query_one):
        """존재하지 않는 직원 조회 시 None 반환"""
        mock_execute_query_one.return_value = None

        result = repo.get_user(999)

        assert result is None

    def test_get_user_passes_correct_id(self, repo, mock_execute_query_one, sample_user):
        """올바른 user_id가 쿼리에 전달되는지 확인"""
        mock_execute_query_one.return_value = sample_user

        repo.get_user(42)

        params = mock_execute_query_one.call_args[0][1]
        assert 42 in params
