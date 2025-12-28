"""AI 평가 서비스 - 일일 기록 평가 비즈니스 로직"""

import json
from typing import Dict, Optional, Any
from modules.clients.daily_prompt import get_evaluation_prompt
from modules.repositories import AiEvaluationRepository
from modules.clients.ai_client import get_ai_client


class EvaluationService:
    """AI 평가 서비스 클래스"""
    
    def __init__(self):
        self.ai_eval_repo = AiEvaluationRepository()
    
    def evaluate_note_with_ai(self, note_text: str, category: str = '', writer: str = '', 
                            customer_name: str = '', date: str = '') -> Optional[Dict]:
        """AI를 사용하여 기록 평가
        
        Args:
            note_text: 평가할 텍스트
            category: 카테고리 (PHYSICAL, COGNITIVE, NURSING, RECOVERY)
            writer: 작성자
            customer_name: 고객명
            date: 날짜
            
        Returns:
            평가 결과 딕셔너리 또는 None
        """
        if not note_text or note_text.strip() in ['특이사항 없음', '결석']:
            return None
        
        try:
            ai_client = get_ai_client()
        except Exception as e:
            print(f'AI 클라이언트 초기화 오류: {e}')
            return None
        
        system_prompt, user_prompt = get_evaluation_prompt(note_text, category, writer, customer_name, date)
        
        try:
            response = ai_client.chat_completion(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.7,
                response_format={'type': 'json_object'}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f'AI 평가 중 오류 발생: {e}')
            return None
    
    def calculate_grade(self, evaluation_result: Dict) -> str:
        """평가 결과로부터 등급 계산
        
        Args:
            evaluation_result: AI 평가 결과
            
        Returns:
            등급 (우수, 평균, 개선)
        """
        if not evaluation_result:
            return '평가없음'
        
        consistency_score = evaluation_result.get('consistency_score', 0)
        grammar_score = evaluation_result.get('grammar_score', 0)
        specificity_score = evaluation_result.get('specificity_score', 0)
        
        average_score = (consistency_score + grammar_score + specificity_score) / 3
        
        if average_score >= 90:
            return '우수'
        elif average_score >= 75:
            return '평균'
        else:
            return '개선'
    
    def create_empty_evaluation(self) -> Dict:
        """빈 평가 결과 생성
        
        Returns:
            기본값이 설정된 빈 평가 결과 딕셔너리
        """
        return {
            'consistency_score': 0,
            'grammar_score': 0,
            'specificity_score': 0,
            'grade_code': '평가없음',
            'reasoning_process': '',
            'suggestion_text': ''
        }
    
    def save_ai_evaluation(self, record_id: int, category: str, note_writer_user_id: int, 
                          evaluation_result: Dict, original_text: str = None) -> None:
        """AI 평가 결과를 데이터베이스에 저장
        
        Args:
            record_id: 기록 ID
            category: 카테고리
            note_writer_user_id: 작성자 사용자 ID
            evaluation_result: 평가 결과
            original_text: 원본 텍스트
        """
        self.ai_eval_repo.save_evaluation(record_id, category, note_writer_user_id, 
                                         evaluation_result, original_text)
    
    def process_daily_note_evaluation(self, record_id: int, category: str, note_text: str, 
                                    note_writer_user_id: int, writer: str = '', 
                                    customer_name: str = '', date: str = '') -> Dict[str, Any]:
        """일일 기록 평가 처리
        
        Args:
            record_id: 기록 ID
            category: 카테고리
            note_text: 평가할 텍스트
            note_writer_user_id: 작성자 사용자 ID
            writer: 작성자
            customer_name: 고객명
            date: 날짜
            
        Returns:
            평가 결과 딕셔너리
        """
        if not note_text or note_text.strip() in ['특이사항 없음', '결석', '']:
            evaluation_result = None
        else:
            evaluation_result = self.evaluate_note_with_ai(note_text, category, writer, customer_name, date)
        
        if evaluation_result:
            # 계산된 등급을 평가 결과에 추가
            korean_grade = self.calculate_grade(evaluation_result)
            evaluation_result['grade_code'] = korean_grade
        else:
            korean_grade = '평가없음'
            # 빈 값이나 특수 경우를 위한 0점 평가 결과 생성
            evaluation_result = self.create_empty_evaluation()
        
        self.save_ai_evaluation(record_id, category, note_writer_user_id, evaluation_result, note_text)
        
        return {
            'grade_code': korean_grade,
            'evaluation': evaluation_result
        }


# 서비스 인스턴스 생성
evaluation_service = EvaluationService()
