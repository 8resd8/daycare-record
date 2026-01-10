"""AiEvaluationRepository 테스트"""

import unittest
import pytest
from unittest.mock import patch
from modules.repositories.ai_evaluation import AiEvaluationRepository


class TestAiEvaluationRepository:
    """AiEvaluationRepository 테스트 클래스"""
    
    @pytest.fixture
    def repo(self):
        """AiEvaluationRepository 인스턴스 생성"""
        return AiEvaluationRepository()
    
    @pytest.fixture
    def mock_execute_query(self):
        """_execute_query 메서드 mock"""
        with patch.object(AiEvaluationRepository, '_execute_query') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_query_one(self):
        """_execute_query_one 메서드 mock"""
        with patch.object(AiEvaluationRepository, '_execute_query_one') as mock:
            yield mock
    
    @pytest.fixture
    def mock_execute_transaction(self):
        """_execute_transaction 메서드 mock"""
        with patch.object(AiEvaluationRepository, '_execute_transaction') as mock:
            yield mock

    # ========== save_evaluation 테스트 ==========
    
    def test_save_evaluation_insert_new(self, repo, mock_execute_query_one, mock_execute_transaction):
        """새 평가 저장 (INSERT)"""
        mock_execute_query_one.return_value = None  # 기존 평가 없음
        mock_execute_transaction.return_value = 1
        
        repo.save_evaluation(
            record_id=100,
            category='PHYSICAL',
            oer_fidelity='O',
            specificity_score='O',
            grammar_score='O',
            grade_code='우수',
            original_text='원본 텍스트',
            reason_text='평가 사유',
            suggestion_text='수정 제안'
        )
        
        # INSERT 쿼리가 실행되었는지 확인
        mock_execute_transaction.assert_called_once()
        call_args = mock_execute_transaction.call_args[0]
        assert 'INSERT' in call_args[0].upper()
    
    def test_save_evaluation_update_existing(self, repo, mock_execute_query_one, mock_execute_transaction):
        """기존 평가 수정 (UPDATE)"""
        mock_execute_query_one.return_value = {'ai_eval_id': 1}  # 기존 평가 있음
        mock_execute_transaction.return_value = 1
        
        repo.save_evaluation(
            record_id=100,
            category='PHYSICAL',
            oer_fidelity='X',
            specificity_score='O',
            grammar_score='X',
            grade_code='개선',
            original_text='수정된 원본',
            reason_text='수정된 사유',
            suggestion_text='수정된 제안'
        )
        
        # UPDATE 쿼리가 실행되었는지 확인
        mock_execute_transaction.assert_called_once()
        call_args = mock_execute_transaction.call_args[0]
        assert 'UPDATE' in call_args[0].upper()
    
    def test_save_evaluation_category_mapping(self, repo, mock_execute_query_one, mock_execute_transaction):
        """영어 카테고리가 한국어로 매핑되는지 확인"""
        mock_execute_query_one.return_value = None
        mock_execute_transaction.return_value = 1
        
        repo.save_evaluation(
            record_id=100,
            category='COGNITIVE',  # 영어 카테고리
            oer_fidelity='O',
            specificity_score='O',
            grammar_score='O',
            grade_code='우수',
            original_text='텍스트'
        )
        
        # 한국어 카테고리 '인지'가 파라미터에 포함되어야 함
        call_args = mock_execute_transaction.call_args[0][1]
        assert '인지' in call_args

    # ========== get_evaluation 테스트 ==========
    
    def test_get_evaluation_exists(self, repo, mock_execute_query_one, sample_evaluation_data):
        """존재하는 평가 조회"""
        mock_execute_query_one.return_value = sample_evaluation_data
        
        result = repo.get_evaluation(record_id=100, category='PHYSICAL')
        
        assert result is not None
        assert result['grade_code'] == '우수'
        assert result['oer_fidelity'] == 'O'
    
    def test_get_evaluation_not_exists(self, repo, mock_execute_query_one):
        """존재하지 않는 평가 조회"""
        mock_execute_query_one.return_value = None
        
        result = repo.get_evaluation(record_id=999, category='PHYSICAL')
        
        assert result is None

    # ========== get_all_evaluations_by_record 테스트 ==========
    
    def test_get_all_evaluations_by_record(self, repo, mock_execute_query, sample_evaluation_data):
        """레코드의 모든 평가 조회"""
        mock_execute_query.return_value = [
            sample_evaluation_data,
            {**sample_evaluation_data, 'category': '인지'}
        ]
        
        result = repo.get_all_evaluations_by_record(record_id=100)
        
        assert len(result) == 2
    
    def test_get_all_evaluations_by_record_empty(self, repo, mock_execute_query):
        """평가가 없는 레코드"""
        mock_execute_query.return_value = []
        
        result = repo.get_all_evaluations_by_record(record_id=999)
        
        assert result == []

    # ========== get_evaluations_by_customer 테스트 ==========
    
    def test_get_evaluations_by_customer(self, repo, mock_execute_query, sample_evaluation_data):
        """고객별 평가 조회"""
        mock_execute_query.return_value = [sample_evaluation_data]
        
        result = repo.get_evaluations_by_customer(customer_id=1, limit=10)
        
        assert len(result) == 1
        mock_execute_query.assert_called_once()

    # ========== delete_evaluation 테스트 ==========
    
    def test_delete_evaluation_success(self, repo, mock_execute_transaction):
        """평가 삭제 성공"""
        mock_execute_transaction.return_value = 1
        
        result = repo.delete_evaluation(record_id=100, category='PHYSICAL')
        
        assert result == 1
    
    def test_delete_evaluation_not_found(self, repo, mock_execute_transaction):
        """존재하지 않는 평가 삭제"""
        mock_execute_transaction.return_value = 0
        
        result = repo.delete_evaluation(record_id=999, category='PHYSICAL')
        
        assert result == 0

    # ========== get_evaluation_stats 테스트 ==========
    
    def test_get_evaluation_stats(self, repo, mock_execute_query):
        """평가 통계 조회"""
        mock_execute_query.return_value = [
            {
                'category': '신체',
                'total_evaluations': 10,
                'avg_oer_fidelity': 0.8,
                'avg_specificity': 0.7,
                'avg_grammar': 0.9,
                'excellent_count': 5,
                'average_count': 3,
                'improvement_count': 2,
                'poor_count': 0
            }
        ]
        
        result = repo.get_evaluation_stats(customer_id=1)
        
        assert '신체' in result
        assert result['신체']['total'] == 10
        assert result['신체']['avg_oer_fidelity'] == 0.8
        assert result['신체']['grades']['우수'] == 5
    
    def test_get_evaluation_stats_with_date_range(self, repo, mock_execute_query):
        """날짜 범위로 평가 통계 조회"""
        mock_execute_query.return_value = []
        
        result = repo.get_evaluation_stats(
            customer_id=1,
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert result == {}
        # 날짜 파라미터가 전달되었는지 확인
        call_args = mock_execute_query.call_args[0][1]
        assert '2024-01-01' in call_args
        assert '2024-01-31' in call_args
