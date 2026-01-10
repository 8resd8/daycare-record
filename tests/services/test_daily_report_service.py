"""EvaluationService 테스트"""

import pytest
from unittest.mock import patch, MagicMock
from modules.services.daily_report_service import EvaluationService


class TestEvaluationService:
    """EvaluationService 테스트 클래스"""
    
    @pytest.fixture
    def service(self):
        """EvaluationService 인스턴스 생성 (repository mocked)"""
        with patch('modules.services.daily_report_service.AiEvaluationRepository') as mock_ai_repo, \
             patch('modules.services.daily_report_service.BaseRepository') as mock_base_repo:
            mock_ai_repo_instance = MagicMock()
            mock_base_repo_instance = MagicMock()
            mock_ai_repo.return_value = mock_ai_repo_instance
            mock_base_repo.return_value = mock_base_repo_instance
            
            svc = EvaluationService()
            svc._mock_ai_repo = mock_ai_repo_instance
            svc._mock_base_repo = mock_base_repo_instance
            yield svc

    # ========== _convert_ox_to_score 테스트 ==========
    
    def test_convert_ox_to_score_excellent(self, service):
        """O 3개 -> 우수 (3점)"""
        evaluation = {
            'oer_fidelity': 'O',
            'specificity': 'O',
            'grammar': 'O'
        }
        
        result = service._convert_ox_to_score(evaluation)
        
        assert result['score'] == 3
        assert result['grade'] == '우수'
    
    def test_convert_ox_to_score_average(self, service):
        """O 2개 -> 평균 (2점)"""
        evaluation = {
            'oer_fidelity': 'O',
            'specificity': 'O',
            'grammar': 'X'
        }
        
        result = service._convert_ox_to_score(evaluation)
        
        assert result['score'] == 2
        assert result['grade'] == '평균'
    
    def test_convert_ox_to_score_improvement(self, service):
        """O 1개 이하 -> 개선 (1점)"""
        evaluation = {
            'oer_fidelity': 'X',
            'specificity': 'O',
            'grammar': 'X'
        }
        
        result = service._convert_ox_to_score(evaluation)
        
        assert result['score'] == 1
        assert result['grade'] == '개선'
    
    def test_convert_ox_to_score_empty(self, service):
        """빈 평가 결과 - 빈 딕셔너리는 그대로 반환"""
        result = service._convert_ox_to_score({})
        
        # 빈 딕셔너리는 그대로 반환됨 (early return)
        assert result == {}
    
    def test_convert_ox_to_score_none(self, service):
        """None 입력"""
        result = service._convert_ox_to_score(None)
        
        assert result is None

    # ========== get_record_id 테스트 ==========
    
    def test_get_record_id_success(self, service):
        """record_id 조회 성공"""
        service._mock_base_repo._execute_query_one.return_value = {'record_id': 100}
        
        result = service.get_record_id('홍길동', '2024-01-15')
        
        assert result == 100
    
    def test_get_record_id_not_found(self, service):
        """record_id 조회 실패"""
        service._mock_base_repo._execute_query_one.return_value = None
        
        result = service.get_record_id('없는고객', '2024-01-15')
        
        assert result is None

    # ========== get_evaluation_from_db 테스트 ==========
    
    def test_get_evaluation_from_db_success(self, service):
        """DB에서 평가 결과 조회 성공"""
        service._mock_base_repo._execute_query_one.return_value = {
            'suggestion_text': '수정 제안',
            'grade_code': '우수'
        }
        
        result = service.get_evaluation_from_db(100, 'SPECIAL_NOTE_PHYSICAL')
        
        assert result['suggestion'] == '수정 제안'
        assert result['grade'] == '우수'
    
    def test_get_evaluation_from_db_not_found(self, service):
        """DB에서 평가 결과 없음"""
        service._mock_base_repo._execute_query_one.return_value = None
        
        result = service.get_evaluation_from_db(999, 'SPECIAL_NOTE_PHYSICAL')
        
        assert result['suggestion'] == ''
        assert result['grade'] == '평가없음'
    
    def test_get_evaluation_from_db_category_mapping(self, service):
        """카테고리 매핑 확인"""
        service._mock_base_repo._execute_query_one.return_value = {
            'suggestion_text': '테스트',
            'grade_code': '평균'
        }
        
        # SPECIAL_NOTE_COGNITIVE -> 인지로 매핑
        service.get_evaluation_from_db(100, 'SPECIAL_NOTE_COGNITIVE')
        
        call_args = service._mock_base_repo._execute_query_one.call_args[0][1]
        assert '인지' in call_args

    # ========== calculate_grade 테스트 ==========
    
    def test_calculate_grade_excellent(self, service):
        """평균 90점 이상 -> 우수"""
        evaluation_result = {
            'consistency_score': 95,
            'grammar_score': 90,
            'specificity_score': 95
        }
        
        result = service.calculate_grade(evaluation_result)
        
        assert result == '우수'
    
    def test_calculate_grade_average(self, service):
        """평균 75점 이상 -> 평균"""
        evaluation_result = {
            'consistency_score': 80,
            'grammar_score': 75,
            'specificity_score': 80
        }
        
        result = service.calculate_grade(evaluation_result)
        
        assert result == '평균'
    
    def test_calculate_grade_improvement(self, service):
        """평균 75점 미만 -> 개선"""
        evaluation_result = {
            'consistency_score': 60,
            'grammar_score': 65,
            'specificity_score': 70
        }
        
        result = service.calculate_grade(evaluation_result)
        
        assert result == '개선'
    
    def test_calculate_grade_empty(self, service):
        """빈 평가 결과 -> 평가없음"""
        result = service.calculate_grade(None)
        
        assert result == '평가없음'

    # ========== create_empty_evaluation 테스트 ==========
    
    def test_create_empty_evaluation(self, service):
        """빈 평가 결과 생성"""
        result = service.create_empty_evaluation()
        
        assert result['oer_fidelity'] == 'X'
        assert result['specificity'] == 'X'
        assert result['grammar'] == 'X'
        assert result['grade_code'] == '평가없음'

    # ========== evaluate_special_note_with_ai 테스트 ==========
    
    def test_evaluate_special_note_with_ai_empty_notes(self, service):
        """빈 특이사항은 평가하지 않음"""
        record = {
            'physical_note': '',
            'cognitive_note': ''
        }
        
        result = service.evaluate_special_note_with_ai(record)
        
        assert result is None
    
    def test_evaluate_special_note_with_ai_success(self, service, sample_ai_response):
        """AI 평가 성공"""
        record = {
            'physical_note': '신체활동 테스트',
            'cognitive_note': '인지관리 테스트'
        }
        
        mock_ai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = sample_ai_response
        mock_ai_client.chat_completion.return_value = mock_response
        
        with patch('modules.services.daily_report_service.get_ai_client', return_value=mock_ai_client):
            with patch('modules.services.daily_report_service.get_special_note_prompt', 
                      return_value=('system prompt', 'user prompt')):
                result = service.evaluate_special_note_with_ai(record)
        
        assert result is not None
        assert 'original_physical' in result
        assert 'original_cognitive' in result
        assert 'physical' in result
        assert 'cognitive' in result
    
    def test_evaluate_special_note_with_ai_client_error(self, service):
        """AI 클라이언트 오류"""
        record = {
            'physical_note': '테스트',
            'cognitive_note': '테스트'
        }
        
        with patch('modules.services.daily_report_service.get_ai_client', side_effect=Exception("API Error")):
            result = service.evaluate_special_note_with_ai(record)
        
        assert result is None

    # ========== _extract_programs_from_text 테스트 ==========
    
    def test_extract_programs_from_text(self, service):
        """텍스트에서 프로그램명 추출"""
        text = "오늘은 두뇌튼튼교실과 힘뇌체조를 진행했습니다."
        
        result = service._extract_programs_from_text(text)
        
        assert '두뇌튼튼교실' in result
        assert '힘뇌체조' in result
    
    def test_extract_programs_from_text_empty(self, service):
        """빈 텍스트"""
        result = service._extract_programs_from_text('')
        
        assert result == []
    
    def test_extract_programs_from_text_none(self, service):
        """None 입력"""
        result = service._extract_programs_from_text(None)
        
        assert result == []

    # ========== save_special_note_evaluation 테스트 ==========
    
    def test_save_special_note_evaluation_success(self, service):
        """특이사항 평가 저장 성공"""
        evaluation_result = {
            'original_physical': {
                'oer_fidelity': 'O',
                'specificity': 'O',
                'grammar': 'O',
                'grade': '우수'
            },
            'original_cognitive': {
                'oer_fidelity': 'O',
                'specificity': 'X',
                'grammar': 'O',
                'grade': '평균'
            },
            'physical': {'corrected_note': '수정된 신체'},
            'cognitive': {'corrected_note': '수정된 인지'},
            'physical_note': '원본 신체',
            'cognitive_note': '원본 인지'
        }
        
        service._mock_base_repo._execute_query_one.return_value = None  # 기존 없음
        service._mock_base_repo._execute_transaction.return_value = 1
        
        # 예외 발생 없이 실행
        service.save_special_note_evaluation(100, evaluation_result)
    
    def test_save_special_note_evaluation_empty(self, service):
        """빈 평가 결과 저장 시도"""
        service.save_special_note_evaluation(100, None)
        # 아무 작업도 수행하지 않음
        service._mock_base_repo._execute_transaction.assert_not_called()

    # ========== process_daily_note_evaluation 테스트 ==========
    
    def test_process_daily_note_evaluation_empty_text(self, service):
        """빈 텍스트 평가"""
        result = service.process_daily_note_evaluation(
            record_id=100,
            category='PHYSICAL',
            note_text='',
            note_writer_user_id=1
        )
        
        assert result['grade_code'] == '평가없음'
        assert result['evaluation'] is None
    
    def test_process_daily_note_evaluation_absent(self, service):
        """결석 상태 평가"""
        result = service.process_daily_note_evaluation(
            record_id=100,
            category='PHYSICAL',
            note_text='결석',
            note_writer_user_id=1
        )
        
        assert result['grade_code'] == '평가없음'
    
    def test_process_daily_note_evaluation_nursing_category(self, service):
        """간호/기능 카테고리는 기본 평가"""
        service._mock_base_repo._execute_query_one.return_value = {
            'record_id': 100,
            'customer_name': '홍길동',
            'physical_note': '',
            'cognitive_note': '',
            'nursing_note': '간호 특이사항',
            'functional_note': ''
        }
        
        result = service.process_daily_note_evaluation(
            record_id=100,
            category='NURSING',
            note_text='간호 특이사항',
            note_writer_user_id=1
        )
        
        assert result['grade_code'] == '평균'


class TestEvaluationServiceIntegration:
    """EvaluationService 통합 테스트 (순수 함수 검증)"""
    
    def test_convert_ox_all_combinations(self):
        """모든 O/X 조합 테스트"""
        service = EvaluationService.__new__(EvaluationService)
        
        test_cases = [
            ({'oer_fidelity': 'O', 'specificity': 'O', 'grammar': 'O'}, 3, '우수'),
            ({'oer_fidelity': 'O', 'specificity': 'O', 'grammar': 'X'}, 2, '평균'),
            ({'oer_fidelity': 'O', 'specificity': 'X', 'grammar': 'O'}, 2, '평균'),
            ({'oer_fidelity': 'X', 'specificity': 'O', 'grammar': 'O'}, 2, '평균'),
            ({'oer_fidelity': 'O', 'specificity': 'X', 'grammar': 'X'}, 1, '개선'),
            ({'oer_fidelity': 'X', 'specificity': 'O', 'grammar': 'X'}, 1, '개선'),
            ({'oer_fidelity': 'X', 'specificity': 'X', 'grammar': 'O'}, 1, '개선'),
            ({'oer_fidelity': 'X', 'specificity': 'X', 'grammar': 'X'}, 1, '개선'),
        ]
        
        for evaluation, expected_score, expected_grade in test_cases:
            result = service._convert_ox_to_score(evaluation.copy())
            assert result['score'] == expected_score, f"Failed for {evaluation}"
            assert result['grade'] == expected_grade, f"Failed for {evaluation}"
    
    def test_extract_programs_various_patterns(self):
        """다양한 프로그램명 패턴 테스트"""
        service = EvaluationService.__new__(EvaluationService)
        
        test_cases = [
            ("오늘은 미술교실을 진행했습니다.", ['미술교실']),
            ("체력향상훈련과 인지활동프로그램 참여", ['체력향상훈련', '인지활동프로그램']),
            ("건강체조 후 미니골프 활동", ['건강체조', '미니골프']),
            ("재난상황 대응훈련을 실시함", ['재난상황 대응훈련']),
        ]
        
        for text, expected in test_cases:
            result = service._extract_programs_from_text(text)
            for program in expected:
                assert any(program in r for r in result), f"Expected '{program}' in {result}"
