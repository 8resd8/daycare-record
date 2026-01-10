"""CustomerRepository 테스트"""

import pytest
from unittest.mock import patch, MagicMock
from modules.repositories.customer import CustomerRepository


class TestCustomerRepository:
    """CustomerRepository 테스트 클래스"""
    
    @pytest.fixture
    def repo(self):
        """CustomerRepository 인스턴스 생성"""
        return CustomerRepository()
    
    @pytest.fixture
    def mock_execute_query(self):
        """_execute_query 메서드 mock"""
        with patch.object(CustomerRepository, '_execute_query') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_query_one(self):
        """_execute_query_one 메서드 mock"""
        with patch.object(CustomerRepository, '_execute_query_one') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_transaction(self):
        """_execute_transaction 메서드 mock"""
        with patch.object(CustomerRepository, '_execute_transaction') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_transaction_lastrowid(self):
        """_execute_transaction_lastrowid 메서드 mock"""
        with patch.object(CustomerRepository, '_execute_transaction_lastrowid') as mock:
            yield mock

    # ========== list_customers 테스트 ==========
    
    def test_list_customers_without_keyword(self, repo, mock_execute_query, sample_customer_data):
        """키워드 없이 전체 고객 목록 조회"""
        mock_execute_query.return_value = [sample_customer_data]
        
        result = repo.list_customers()
        
        assert len(result) == 1
        assert result[0]['name'] == '홍길동'
        mock_execute_query.assert_called_once()
    
    def test_list_customers_with_keyword(self, repo, mock_execute_query, sample_customer_data):
        """키워드로 고객 검색"""
        mock_execute_query.return_value = [sample_customer_data]
        
        result = repo.list_customers(keyword='홍')
        
        assert len(result) == 1
        mock_execute_query.assert_called_once()
        call_args = mock_execute_query.call_args
        assert '%홍%' in call_args[0][1]
    
    def test_list_customers_empty_result(self, repo, mock_execute_query):
        """고객이 없는 경우"""
        mock_execute_query.return_value = []
        
        result = repo.list_customers()
        
        assert result == []

    # ========== get_customer 테스트 ==========
    
    def test_get_customer_exists(self, repo, mock_execute_query_one, sample_customer_data):
        """존재하는 고객 조회"""
        mock_execute_query_one.return_value = sample_customer_data
        
        result = repo.get_customer(1)
        
        assert result is not None
        assert result['customer_id'] == 1
        assert result['name'] == '홍길동'
    
    def test_get_customer_not_exists(self, repo, mock_execute_query_one):
        """존재하지 않는 고객 조회"""
        mock_execute_query_one.return_value = None
        
        result = repo.get_customer(999)
        
        assert result is None

    # ========== create_customer 테스트 ==========
    
    def test_create_customer_success(self, repo, mock_execute_transaction_lastrowid):
        """고객 생성 성공"""
        mock_execute_transaction_lastrowid.return_value = 1
        
        result = repo.create_customer(
            name='김철수',
            birth_date='1960-05-15',
            gender='M',
            recognition_no='L9876543210',
            grade='2등급'
        )
        
        assert result == 1
        mock_execute_transaction_lastrowid.assert_called_once()

    # ========== update_customer 테스트 ==========
    
    def test_update_customer_success(self, repo, mock_execute_transaction):
        """고객 정보 수정 성공"""
        mock_execute_transaction.return_value = 1
        
        result = repo.update_customer(
            customer_id=1,
            name='홍길동',
            birth_date='1950-01-01',
            gender='M',
            grade='2등급'
        )
        
        assert result == 1
    
    def test_update_customer_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 고객 수정"""
        mock_execute_transaction.return_value = 0
        
        result = repo.update_customer(
            customer_id=999,
            name='없는고객',
            birth_date='2000-01-01'
        )
        
        assert result == 0

    # ========== delete_customer 테스트 ==========
    
    def test_delete_customer_success(self, repo, mock_execute_transaction):
        """고객 삭제 성공"""
        mock_execute_transaction.return_value = 1
        
        result = repo.delete_customer(1)
        
        assert result == 1
    
    def test_delete_customer_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 고객 삭제"""
        mock_execute_transaction.return_value = 0
        
        result = repo.delete_customer(999)
        
        assert result == 0

    # ========== find_by_name 테스트 ==========
    
    def test_find_by_name_exists(self, repo, mock_execute_query_one, sample_customer_data):
        """이름으로 고객 검색 - 존재"""
        mock_execute_query_one.return_value = sample_customer_data
        
        result = repo.find_by_name('홍길동')
        
        assert result is not None
        assert result['name'] == '홍길동'
    
    def test_find_by_name_not_exists(self, repo, mock_execute_query_one):
        """이름으로 고객 검색 - 존재하지 않음"""
        mock_execute_query_one.return_value = None
        
        result = repo.find_by_name('없는이름')
        
        assert result is None

    # ========== find_by_recognition_no 테스트 ==========
    
    def test_find_by_recognition_no_exists(self, repo, mock_execute_query_one, sample_customer_data):
        """인정번호로 고객 검색 - 존재"""
        mock_execute_query_one.return_value = sample_customer_data
        
        result = repo.find_by_recognition_no('L1234567890')
        
        assert result is not None
        assert result['recognition_no'] == 'L1234567890'

    # ========== get_or_create 테스트 ==========
    
    def test_get_or_create_existing_customer(self, repo, mock_execute_query_one, mock_execute_transaction, sample_customer_data):
        """기존 고객이 있으면 업데이트 후 ID 반환"""
        mock_execute_query_one.return_value = sample_customer_data
        mock_execute_transaction.return_value = 1
        
        result = repo.get_or_create(name='홍길동', birth_date='1950-01-01')
        
        assert result == 1
    
    def test_get_or_create_new_customer(self, repo, mock_execute_query_one, mock_execute_transaction_lastrowid):
        """새 고객이면 생성 후 ID 반환"""
        mock_execute_query_one.return_value = None
        mock_execute_transaction_lastrowid.return_value = 2
        
        result = repo.get_or_create(name='새고객', birth_date='1970-01-01')
        
        assert result == 2
