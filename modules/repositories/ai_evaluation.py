"""AI evaluation repository for database operations."""

from typing import Dict, Optional
from .base import BaseRepository


class AiEvaluationRepository(BaseRepository):
    """Repository for AI evaluation operations."""
    
    def save_evaluation(self, record_id: int, category: str, 
                       oer_fidelity: str, specificity_score: str, grammar_score: str,
                       grade_code: str, original_text: str, reason_text: str = None,
                       suggestion_text: str = None) -> None:
        """Save or update AI evaluation result."""
        # 영어 카테고리를 한국어로 매핑
        category_map = {
            "PHYSICAL": "신체",
            "COGNITIVE": "인지", 
            "NURSING": "간호",
            "RECOVERY": "기능",
            "SPECIAL_NOTE_PHYSICAL": "신체",
            "SPECIAL_NOTE_COGNITIVE": "인지"
        }
        korean_category = category_map.get(category, category)
        
        # 평가가 존재하는지 확인
        check_query = 'SELECT ai_eval_id FROM ai_evaluations WHERE record_id = %s AND category = %s'
        existing = self._execute_query_one(check_query, (record_id, korean_category))
        
        if existing:
            # 기존 평가 업데이트
            update_query = '''
                UPDATE ai_evaluations SET
                    oer_fidelity = %s,
                    specificity_score = %s,
                    grammar_score = %s,
                    grade_code = %s,
                    reason_text = %s,
                    suggestion_text = %s,
                    original_text = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE record_id = %s AND category = %s
            '''
            self._execute_transaction(update_query, (
                oer_fidelity, specificity_score, grammar_score,
                grade_code, reason_text, suggestion_text, original_text,
                record_id, korean_category
            ))
        else:
            # 새 평가 삽입
            insert_query = '''
                INSERT INTO ai_evaluations (
                    record_id, category, oer_fidelity, specificity_score, grammar_score,
                    grade_code, reason_text, suggestion_text, original_text, 
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            '''
            self._execute_transaction(insert_query, (
                record_id, korean_category, oer_fidelity, specificity_score, grammar_score,
                grade_code, reason_text, suggestion_text, original_text
            ))
    
    def get_evaluation(self, record_id: int, category: str) -> Optional[Dict]:
        """Get AI evaluation for a specific record and category."""
        category_map = {
            "PHYSICAL": "신체",
            "COGNITIVE": "인지", 
            "NURSING": "간호",
            "RECOVERY": "기능"
        }
        korean_category = category_map.get(category, category)
        
        query = """
            SELECT ai_eval_id, oer_fidelity, specificity_score, grammar_score,
                   grade_code, reason_text, suggestion_text, original_text,
                   created_at, updated_at
            FROM ai_evaluations
            WHERE record_id = %s AND category = %s
        """
        return self._execute_query_one(query, (record_id, korean_category))
    
    def get_all_evaluations_by_record(self, record_id: int) -> list:
        """Get all AI evaluations for a record."""
        query = """
            SELECT category, oer_fidelity, specificity_score, grammar_score,
                   grade_code, reason_text, suggestion_text, created_at
            FROM ai_evaluations
            WHERE record_id = %s
            ORDER BY category
        """
        return self._execute_query(query, (record_id,))
    
    def get_evaluations_by_customer(self, customer_id: int, limit: int = 50) -> list:
        """Get recent AI evaluations for a customer."""
        query = """
            SELECT 
                ae.category, ae.oer_fidelity, ae.specificity_score,
                ae.grammar_score, ae.grade_code, ae.reason_text,
                ae.suggestion_text, ae.created_at,
                di.date, c.name as customer_name
            FROM ai_evaluations ae
            JOIN daily_infos di ON ae.record_id = di.record_id
            JOIN customers c ON di.customer_id = c.customer_id
            WHERE c.customer_id = %s
            ORDER BY di.date DESC, ae.created_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (customer_id, limit))
    
    def delete_evaluation(self, record_id: int, category: str) -> int:
        """Delete an AI evaluation."""
        category_map = {
            "PHYSICAL": "신체",
            "COGNITIVE": "인지", 
            "NURSING": "간호",
            "RECOVERY": "기능"
        }
        korean_category = category_map.get(category, category)
        
        query = "DELETE FROM ai_evaluations WHERE record_id = %s AND category = %s"
        return self._execute_transaction(query, (record_id, korean_category))
    
    def get_evaluation_stats(self, customer_id: int, start_date=None, end_date=None) -> Dict:
        """Get evaluation statistics for a customer within date range."""
        query = """
            SELECT 
                ae.category,
                COUNT(*) as total_evaluations,
                AVG(CASE WHEN ae.oer_fidelity = 'O' THEN 1 ELSE 0 END) as avg_oer_fidelity,
                AVG(CASE WHEN ae.specificity_score = 'O' THEN 1 ELSE 0 END) as avg_specificity,
                AVG(CASE WHEN ae.grammar_score = 'O' THEN 1 ELSE 0 END) as avg_grammar,
                SUM(CASE WHEN ae.grade_code = '우수' THEN 1 ELSE 0 END) as excellent_count,
                SUM(CASE WHEN ae.grade_code = '평균' THEN 1 ELSE 0 END) as average_count,
                SUM(CASE WHEN ae.grade_code = '개선' THEN 1 ELSE 0 END) as improvement_count,
                SUM(CASE WHEN ae.grade_code = '불량' THEN 1 ELSE 0 END) as poor_count
            FROM ai_evaluations ae
            JOIN daily_infos di ON ae.record_id = di.record_id
            WHERE di.customer_id = %s
        """
        params = [customer_id]
        
        if start_date and end_date:
            query += " AND di.date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += " GROUP BY ae.category"
        
        results = self._execute_query(query, tuple(params))
        
        # 결과 포맷팅
        stats = {}
        for row in results:
            stats[row['category']] = {
                'total': row['total_evaluations'],
                'avg_oer_fidelity': round(row['avg_oer_fidelity'], 2) if row['avg_oer_fidelity'] else 0,
                'avg_specificity': round(row['avg_specificity'], 2) if row['avg_specificity'] else 0,
                'avg_grammar': round(row['avg_grammar'], 2) if row['avg_grammar'] else 0,
                'grades': {
                    '우수': row['excellent_count'],
                    '평균': row['average_count'],
                    '개선': row['improvement_count'],
                    '불량': row['poor_count']
                }
            }
        
        return stats
