"""EmployeeEvaluationRepository 테스트"""

import pytest
from unittest.mock import patch
from datetime import date
from modules.repositories.employee_evaluation import EmployeeEvaluationRepository


class TestEmployeeEvaluationRepository:
    """EmployeeEvaluationRepository 테스트 클래스"""
    
    @pytest.fixture
    def repo(self):
        """EmployeeEvaluationRepository 인스턴스 생성"""
        return EmployeeEvaluationRepository()
    
    @pytest.fixture
    def mock_execute_query(self):
        """_execute_query 메서드 mock"""
        with patch.object(EmployeeEvaluationRepository, '_execute_query') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_query_one(self):
        """_execute_query_one 메서드 mock"""
        with patch.object(EmployeeEvaluationRepository, '_execute_query_one') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_transaction(self):
        """_execute_transaction 메서드 mock"""
        with patch.object(EmployeeEvaluationRepository, '_execute_transaction') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_transaction_lastrowid(self):
        """_execute_transaction_lastrowid 메서드 mock"""
        with patch.object(EmployeeEvaluationRepository, '_execute_transaction_lastrowid') as mock:
            yield mock

    # ========== save_evaluation 테스트 ==========
    
    def test_save_evaluation_success(self, repo, mock_execute_transaction_lastrowid):
        """직원 평가 저장 성공"""
        mock_execute_transaction_lastrowid.return_value = 1
        
        result = repo.save_evaluation(
            record_id=100,
            target_user_id=1,
            category='신체',
            evaluation_type='누락',
            evaluation_date=date(2024, 1, 15),
            evaluator_user_id=2,
            score=1,
            comment='테스트 코멘트'
        )
        
        assert result == 1
        mock_execute_transaction_lastrowid.assert_called_once()
    
    def test_save_evaluation_without_optional_fields(self, repo, mock_execute_transaction_lastrowid):
        """선택적 필드 없이 평가 저장"""
        mock_execute_transaction_lastrowid.return_value = 2
        
        result = repo.save_evaluation(
            record_id=100,
            target_user_id=1,
            category='인지',
            evaluation_type='내용부족',
            evaluation_date=date(2024, 1, 15)
        )
        
        assert result == 2

    # ========== get_evaluations_by_record 테스트 ==========
    
    def test_get_evaluations_by_record(self, repo, mock_execute_query, sample_employee_evaluation_data):
        """레코드별 직원 평가 조회"""
        mock_execute_query.return_value = [
            {**sample_employee_evaluation_data, 'target_user_name': '홍길동', 'evaluator_user_name': '김철수'}
        ]
        
        result = repo.get_evaluations_by_record(record_id=100)
        
        assert len(result) == 1
        assert result[0]['target_user_name'] == '홍길동'
    
    def test_get_evaluations_by_record_empty(self, repo, mock_execute_query):
        """평가가 없는 레코드"""
        mock_execute_query.return_value = []
        
        result = repo.get_evaluations_by_record(record_id=999)
        
        assert result == []

    # ========== get_user_id_by_name 테스트 ==========
    
    def test_get_user_id_by_name_exists(self, repo, mock_execute_query_one):
        """존재하는 사용자 ID 조회"""
        mock_execute_query_one.return_value = {'user_id': 1}
        
        result = repo.get_user_id_by_name('홍길동')
        
        assert result == 1
    
    def test_get_user_id_by_name_not_exists(self, repo, mock_execute_query_one):
        """존재하지 않는 사용자"""
        mock_execute_query_one.return_value = None
        
        result = repo.get_user_id_by_name('없는사용자')
        
        assert result is None

    # ========== get_all_users 테스트 ==========
    
    def test_get_all_users(self, repo, mock_execute_query):
        """모든 사용자 조회"""
        mock_execute_query.return_value = [
            {'user_id': 1, 'name': '홍길동'},
            {'user_id': 2, 'name': '김철수'}
        ]
        
        result = repo.get_all_users()
        
        assert len(result) == 2
        assert result[0]['name'] == '홍길동'

    # ========== delete_evaluation 테스트 ==========
    
    def test_delete_evaluation_success(self, repo, mock_execute_transaction):
        """평가 삭제 성공"""
        mock_execute_transaction.return_value = 1
        
        result = repo.delete_evaluation(emp_eval_id=1)
        
        assert result == 1
    
    def test_delete_evaluation_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 평가 삭제"""
        mock_execute_transaction.return_value = 0
        
        result = repo.delete_evaluation(emp_eval_id=999)
        
        assert result == 0

    # ========== find_existing_evaluation 테스트 ==========
    
    def test_find_existing_evaluation_exists(self, repo, mock_execute_query_one):
        """기존 평가 찾기 - 존재"""
        mock_execute_query_one.return_value = {'emp_eval_id': 5}
        
        result = repo.find_existing_evaluation(
            record_id=100,
            target_user_id=1,
            category='신체',
            evaluation_type='누락'
        )
        
        assert result == 5
    
    def test_find_existing_evaluation_not_exists(self, repo, mock_execute_query_one):
        """기존 평가 찾기 - 존재하지 않음"""
        mock_execute_query_one.return_value = None
        
        result = repo.find_existing_evaluation(
            record_id=100,
            target_user_id=1,
            category='신체',
            evaluation_type='누락'
        )
        
        assert result is None

    # ========== update_evaluation 테스트 ==========
    
    def test_update_evaluation_success(self, repo, mock_execute_transaction):
        """평가 수정 성공"""
        mock_execute_transaction.return_value = 1
        
        result = repo.update_evaluation(
            emp_eval_id=1,
            evaluation_date=date(2024, 1, 20),
            evaluator_user_id=2,
            score=2,
            comment='수정된 코멘트'
        )
        
        assert result == 1
    
    def test_update_evaluation_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 평가 수정"""
        mock_execute_transaction.return_value = 0
        
        result = repo.update_evaluation(
            emp_eval_id=999,
            evaluation_date=date(2024, 1, 20)
        )
        
        assert result == 0
