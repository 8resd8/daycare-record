"""AI 일일 평가 모듈 - 서비스 레이어 위임"""

# 서비스 레이어로 위임하기 위한 하위 호환성 래퍼
from modules.services.daily_report_service import evaluation_service

# 이전 API와의 호환성을 위한 함수들
def evaluate_note_with_ai(note_text: str, category: str = '', writer: str = '', customer_name: str = '', date: str = ''):
    """AI를 사용하여 기록 평가 (서비스 위임)"""
    return evaluation_service.evaluate_note_with_ai(note_text, category, writer, customer_name, date)

def save_ai_evaluation(record_id: int, category: str, note_writer_user_id: int, evaluation_result: dict, original_text: str = None):
    """AI 평가 결과 저장 (서비스 위임)"""
    evaluation_service.save_ai_evaluation(record_id, category, note_writer_user_id, evaluation_result, original_text)

def process_daily_note_evaluation(record_id: int, category: str, note_text: str, note_writer_user_id: int, writer: str = '', customer_name: str = '', date: str = ''):
    """일일 기록 평가 처리 (서비스 위임)"""
    return evaluation_service.process_daily_note_evaluation(record_id, category, note_text, note_writer_user_id, writer, customer_name, date)
