import streamlit as st
import json
from daily_prompt import get_evaluation_prompt
from modules.repositories import AiEvaluationRepository
from modules.ai_client import get_ai_client


# Initialize repository
ai_eval_repo = AiEvaluationRepository()


def evaluate_note_with_ai(note_text: str, category: str = '', writer: str = '', customer_name: str = '', date: str = ''):
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


def save_ai_evaluation(record_id: int, category: str, note_writer_user_id: int, evaluation_result: dict, original_text: str = None):
    """Save AI evaluation result to database."""
    ai_eval_repo.save_evaluation(record_id, category, note_writer_user_id, evaluation_result, original_text)


def process_daily_note_evaluation(record_id: int, category: str, note_text: str, note_writer_user_id: int, writer: str = '', customer_name: str = '', date: str = ''):
    """Process daily note evaluation with AI and save to database."""
    if not note_text or note_text.strip() in ['특이사항 없음', '결석', '']:
        evaluation_result = None
    else:
        evaluation_result = evaluate_note_with_ai(note_text, category, writer, customer_name, date)
    
    if evaluation_result:
        # 서버에서 점수 기반 등급 계산
        consistency_score = evaluation_result.get('consistency_score', 0)
        grammar_score = evaluation_result.get('grammar_score', 0)
        specificity_score = evaluation_result.get('specificity_score', 0)
        
        average_score = (consistency_score + grammar_score + specificity_score) / 3
        
        if average_score >= 90:
            korean_grade = '우수'
        elif average_score >= 75:
            korean_grade = '평균'
        else:
            korean_grade = '개선'
        
        # 계산된 등급을 평가 결과에 추가
        evaluation_result['grade_code'] = korean_grade
    else:
        korean_grade = '평가없음'
        # 빈 값이나 특수 경우를 위한 0점 평가 결과 생성
        evaluation_result = {
            'consistency_score': 0,
            'grammar_score': 0,
            'specificity_score': 0,
            'grade_code': '평가없음',
            'reasoning_process': '',
            'suggestion_text': ''
        }
    
    save_ai_evaluation(record_id, category, note_writer_user_id, evaluation_result, note_text)
    
    return {
        'grade_code': korean_grade,  # Return Korean grade
        'evaluation': evaluation_result
    }
