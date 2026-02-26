"""AI 평가 서비스 - 일일 기록 평가 비즈니스 로직"""

import json
import re
from typing import Dict, Optional, Any, List
from modules.clients.daily_prompt import get_special_note_prompt
from modules.repositories import AiEvaluationRepository
from modules.repositories.base import BaseRepository
from modules.clients.ai_client import get_ai_client
import numpy as np


class EvaluationService:
    """AI 평가 서비스 클래스"""
    
    def __init__(self):
        self.ai_eval_repo = AiEvaluationRepository()
        self.db_repo = BaseRepository()
    
    def _convert_ox_to_score(self, evaluation: dict) -> dict:
        """O/X 평가 결과를 점수로 변환
        
        Args:
            evaluation: O/X 평가 결과가 포함된 딕셔너리
            
        Returns:
            점수(3-우수, 2-평균, 1-개선)와 등급이 추가된 딕셔너리
        """
        if not evaluation:
            return evaluation
        
        # O 개수 세기
        o_count = 0
        for metric in ['oer_fidelity', 'specificity', 'grammar']:
            if evaluation.get(metric) == 'O':
                o_count += 1
        
        # 점수와 등급 결정
        if o_count == 3:
            score = 3
            grade = '우수'
        elif o_count == 2:
            score = 2
            grade = '평균'
        else:
            score = 1
            grade = '개선'
        
        # 점수와 등급 추가
        evaluation['score'] = score
        evaluation['grade'] = grade
        
        return evaluation
    
        
    def save_special_note_evaluation(self, record_id: int, evaluation_result: dict) -> None:
        """특이사항 평가 결과를 DB에 저장
        
        Args:
            record_id: 일일 기록 ID
            evaluation_result: AI 평가 결과
        """
        if not evaluation_result:
            return
            
        # 신체활동 특이사항 저장
        if 'original_physical' in evaluation_result:
            physical = evaluation_result['original_physical']
            self._save_evaluation_to_db(
                record_id, 'SPECIAL_NOTE_PHYSICAL',
                physical.get('oer_fidelity', 'X'),
                physical.get('specificity', 'X'),
                physical.get('grammar', 'X'),
                physical.get('grade', '개선'),
                evaluation_result.get('physical_note', ''),
                None,  # reason_text
                evaluation_result.get('physical', {}).get('corrected_note', '')
            )
        
        # 인지관리 특이사항 저장
        if 'original_cognitive' in evaluation_result:
            cognitive = evaluation_result['original_cognitive']
            self._save_evaluation_to_db(
                record_id, 'SPECIAL_NOTE_COGNITIVE',
                cognitive.get('oer_fidelity', 'X'),
                cognitive.get('specificity', 'X'),
                cognitive.get('grammar', 'X'),
                cognitive.get('grade', '개선'),
                evaluation_result.get('cognitive_note', ''),
                None,  # reason_text
                evaluation_result.get('cognitive', {}).get('corrected_note', '')
            )
    
    def _save_evaluation_to_db(self, record_id: int, category: str,
                              oer_fidelity: str, specificity: str, grammar: str,
                              grade: str, original_text: str, reason_text: str,
                              suggestion_text: str) -> None:
        """개별 평가 결과를 DB에 저장"""
        # 카테고리 매핑
        category_map = {
            "SPECIAL_NOTE_PHYSICAL": "신체",
            "SPECIAL_NOTE_COGNITIVE": "인지"
        }
        korean_category = category_map.get(category, category)
        
        # 기존 평가 확인
        check_query = 'SELECT ai_eval_id FROM ai_evaluations WHERE record_id = %s AND category = %s'
        existing = self.db_repo._execute_query_one(check_query, (record_id, korean_category))
        
        if existing:
            # 업데이트
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
            self.db_repo._execute_transaction(update_query, (
                oer_fidelity, specificity, grammar, grade,
                reason_text, suggestion_text, original_text,
                record_id, korean_category
            ))
        else:
            # 삽입
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
            self.db_repo._execute_transaction(insert_query, (
                record_id, korean_category, oer_fidelity, specificity,
                grammar, grade, reason_text, suggestion_text, original_text
            ))
    
    def get_record_id(self, customer_name: str, date: str) -> Optional[int]:
        """고객명과 날짜로 record_id 조회"""
        print(f"DEBUG: get_record_id 호출 - customer_name={customer_name}, date={date}")
        
        query = '''
            SELECT di.record_id 
            FROM daily_infos di
            JOIN customers c ON di.customer_id = c.customer_id
            WHERE c.name = %s AND di.date = %s
        '''
        result = self.db_repo._execute_query_one(query, (customer_name, date))
        
        if result:
            print(f"DEBUG: record_id 조회 성공 - {result['record_id']}")
        else:
            print(f"DEBUG: record_id 조회 실패 - 결과 없음")
            
        return result['record_id'] if result else None
    
    def get_evaluation_from_db(self, record_id: int, category: str) -> Dict[str, str]:
        """DB에서 평가 결과(수정 제안과 등급) 조회
        
        Args:
            record_id: 일일 기록 ID
            category: 카테고리 (SPECIAL_NOTE_PHYSICAL 또는 SPECIAL_NOTE_COGNITIVE)
            
        Returns:
            {'suggestion': str, 'grade': str} 형태의 딕셔너리
        """
        # 카테고리 매핑
        category_map = {
            "SPECIAL_NOTE_PHYSICAL": "신체",
            "SPECIAL_NOTE_COGNITIVE": "인지"
        }
        korean_category = category_map.get(category, category)
        
        query = '''
            SELECT suggestion_text, grade_code 
            FROM ai_evaluations 
            WHERE record_id = %s AND category = %s
        '''
        result = self.db_repo._execute_query_one(query, (record_id, korean_category))
        
        if result:
            return {
                'suggestion': result['suggestion_text'] or '',
                'grade': result['grade_code'] or '평가없음'
            }
        else:
            return {
                'suggestion': '',
                'grade': '평가없음'
            }
    
    def evaluate_special_note_with_ai(self, record: dict) -> Optional[Dict]:
        """XML 형식으로 특이사항 평가
        
        Args:
            record: 전체 기록 딕셔너리
            
        Returns:
            평가 결과 딕셔너리 또는 None
        """
        physical_note = record.get('physical_note', '')
        cognitive_note = record.get('cognitive_note', '')
        
        if not physical_note and not cognitive_note:
            return None
        
        try:
            ai_client = get_ai_client(provider='gemini')
        except Exception as e:
            print(f'AI 클라이언트 초기화 오류: {e}')
            return None
        
        system_prompt, user_prompt = get_special_note_prompt(record)
        
        try:
            response = ai_client.chat_completion(
                model='gemini-3-flash-preview',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.7
            )
            
            # JSON 응답 파싱
            content = response.choices[0].message.content
            # 코드 블록 제거
            if content.startswith('```json'):
                content = content[7:-3].strip()
            elif content.startswith('```'):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            
            # AI 결과 디버그 출력
            print("=" * 50)
            print("DEBUG: AI 평가 결과")
            print("=" * 50)
            print("원본 신체활동 평가:", result.get("original_physical_evaluation", {}))
            print("원본 인지관리 평가:", result.get("original_cognitive_evaluation", {}))
            print("생성된 신체활동:", result["physical_candidates"][0])
            print("생성된 인지관리:", result["cognitive_candidates"][0])
            print("\n[O/X 평가 결과]")
            print(f"원본 신체: OER={result.get('original_physical_evaluation', {}).get('oer_fidelity', '-')}, "
                  f"구체성={result.get('original_physical_evaluation', {}).get('specificity', '-')}, "
                  f"문법={result.get('original_physical_evaluation', {}).get('grammar', '-')}")
            print(f"원본 인지: OER={result.get('original_cognitive_evaluation', {}).get('oer_fidelity', '-')}, "
                  f"구체성={result.get('original_cognitive_evaluation', {}).get('specificity', '-')}, "
                  f"문법={result.get('original_cognitive_evaluation', {}).get('grammar', '-')}")
            print("=" * 50)
            
            # 3개 후보 중에서 첫 번째 선택 (날짜별 독립 처리)
            result = {
                "original_physical": result.get("original_physical_evaluation", {}),
                "original_cognitive": result.get("original_cognitive_evaluation", {}),
                "physical": result["physical_candidates"][0],
                "cognitive": result["cognitive_candidates"][0]
            }
            
            # O/X 평가 결과를 점수로 변환
            result["original_physical"] = self._convert_ox_to_score(result["original_physical"])
            result["original_cognitive"] = self._convert_ox_to_score(result["original_cognitive"])
            result["physical"] = self._convert_ox_to_score(result["physical"])
            result["cognitive"] = self._convert_ox_to_score(result["cognitive"])
            
            return result
        except Exception as e:
            print(f'특이사항 AI 평가 중 오류 발생: {e}')
            return None
    
    def _extract_programs_from_text(self, text: str) -> List[str]:
        """텍스트에서 프로그램명을 추출"""
        if not text:
            return []
        
        # 일반적인 프로그램명 패턴
        patterns = [
            r'([가-힣]+교실)',
            r'([가-힣]+훈련)',
            r'([가-힣]+프로그램)',
            r'([가-힣]+활동)',
            r'([가-힣]+체조)',
            r'([가-힣]+노래자랑)',
            r'([가-힣]+워크북)',
            r'([가-힣]+관리)',
            r'재난상황\s*대응훈련',
            r'두뇌튼튼교실',
            r'보은노래자랑',
            r'힘뇌체조',
            r'미니골프',
            r'인지활동형프로그램'
        ]
        
        programs = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match and match not in programs:
                    programs.append(match)
        
        return programs
    
    def _select_most_unique_sentences(self, result: Dict, previous_sentences: List[str]) -> Dict:
        """3개 후보 중에서 이전 문장들과 가장 유사도가 낮은 문장 선택"""
        if not previous_sentences:
            # 이전 문장이 없으면 첫 번째 후보 선택
            return {
                "physical": result["physical_candidates"][0],
                "cognitive": result["cognitive_candidates"][0]
            }

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except Exception:
            # scikit-learn / scipy 네이티브 확장 로딩 실패(또는 미설치) 시 fallback
            return {
                "physical": result["physical_candidates"][0],
                "cognitive": result["cognitive_candidates"][0]
            }
        
        # TF-IDF 벡터라이저 초기화
        vectorizer = TfidfVectorizer()
        
        # physical 후보 중 가장 유사도 낮은 것 선택
        physical_sentences = [candidate["corrected_note"] for candidate in result["physical_candidates"]]
        physical_selected = self._find_least_similar(
            physical_sentences, previous_sentences, vectorizer
        )
        
        # cognitive 후보 중 가장 유사도 낮은 것 선택
        cognitive_sentences = [candidate["corrected_note"] for candidate in result["cognitive_candidates"]]
        cognitive_selected = self._find_least_similar(
            cognitive_sentences, previous_sentences, vectorizer
        )
        
        # 선택된 후보의 원래 인덱스 찾기
        physical_idx = physical_sentences.index(physical_selected)
        cognitive_idx = cognitive_sentences.index(cognitive_selected)
        
        return {
            "physical": result["physical_candidates"][physical_idx],
            "cognitive": result["cognitive_candidates"][cognitive_idx]
        }
    
    def _find_least_similar(self, candidates: List[str], references: List[str], 
                           vectorizer: Any) -> str:
        """후보 중에서 참조 문장들과 가장 유사도가 낮은 문장 찾기"""
        if not references:
            return candidates[0]

        try:
            from sklearn.metrics.pairwise import cosine_similarity
        except Exception:
            # scikit-learn / scipy 네이티브 확장 로딩 실패(또는 미설치) 시 fallback
            return candidates[0]
        
        # 모든 문장 결합하여 TF-IDF 벡터 생성
        all_sentences = candidates + references
        tfidf_matrix = vectorizer.fit_transform(all_sentences)
        
        # 후보 문장들의 벡터 (첫 n개)
        candidate_vectors = tfidf_matrix[:len(candidates)]
        
        # 참조 문장들의 벡터
        reference_vectors = tfidf_matrix[len(candidates):]
        
        # 각 후보와 참조 문장들 간의 평균 유사도 계산
        similarities = []
        for i in range(len(candidates)):
            candidate_vec = candidate_vectors[i]
            # 참조 문장들과의 유사도 계산
            sim_scores = cosine_similarity(candidate_vec, reference_vectors)[0]
            # 평균 유사도
            avg_similarity = np.mean(sim_scores)
            similarities.append(avg_similarity)
        
        # 가장 유사도가 낮은 후보 선택
        min_sim_idx = np.argmin(similarities)
        return candidates[min_sim_idx]
    
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
            'oer_fidelity': 'X',
            'specificity': 'X',
            'grammar': 'X',
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
        # evaluation_result에서 점수 정보 추출
        if evaluation_result:
            oer_fidelity = evaluation_result.get('oer_fidelity', 'X')
            # specificity와 specificity_score 모두 지원
            specificity_score = evaluation_result.get('specificity_score') or evaluation_result.get('specificity', 'X')
            # grammar와 grammar_score 모두 지원
            grammar_score = evaluation_result.get('grammar_score') or evaluation_result.get('grammar', 'X')
            grade_code = evaluation_result.get('grade_code', '평가없음')
            reason_text = evaluation_result.get('reasoning_process', '') or evaluation_result.get('reason', '')
            suggestion_text = evaluation_result.get('suggestion_text', '') or evaluation_result.get('corrected_note', '')
        else:
            oer_fidelity = 'X'
            specificity_score = 'X'
            grammar_score = 'X'
            grade_code = '평가없음'
            reason_text = ''
            suggestion_text = ''
        
        self.ai_eval_repo.save_evaluation(
            record_id, category, oer_fidelity, specificity_score, grammar_score,
            grade_code, original_text or '', reason_text, suggestion_text
        )
    
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
            # 빈 텍스트는 평가하지 않음
            return {
                'grade_code': '평가없음',
                'evaluation': None
            }
        
        # DB에서 record 정보 가져오기
        query = '''
            SELECT di.*, c.name as customer_name,
                   dp.note as physical_note, dc.note as cognitive_note,
                   dn.note as nursing_note, dr.note as functional_note
            FROM daily_infos di
            LEFT JOIN customers c ON di.customer_id = c.customer_id
            LEFT JOIN daily_physicals dp ON dp.record_id = di.record_id
            LEFT JOIN daily_cognitives dc ON dc.record_id = di.record_id
            LEFT JOIN daily_nursings dn ON dn.record_id = di.record_id
            LEFT JOIN daily_recoveries dr ON dr.record_id = di.record_id
            WHERE di.record_id = %s
        '''
        record = self.db_repo._execute_query_one(query, (record_id,))
        
        if not record:
            # record가 없으면 평가하지 않음
            return {
                'grade_code': '평가없음',
                'evaluation': None
            }
        
        # PHYSICAL, COGNITIVE만 AI 평가
        if category in ['PHYSICAL', 'COGNITIVE']:
            # evaluate_special_note_with_ai 호출
            ai_result = self.evaluate_special_note_with_ai(record)
            
            if ai_result:
                # 카테고리에 맞는 평가 결과 추출
                if category == 'PHYSICAL':
                    evaluation_result = ai_result.get('original_physical', {})
                    # 수정 제안(corrected_note)도 포함
                    corrected_note = ai_result.get('physical', {}).get('corrected_note', '')
                elif category == 'COGNITIVE':
                    evaluation_result = ai_result.get('original_cognitive', {})
                    # 수정 제안(corrected_note)도 포함
                    corrected_note = ai_result.get('cognitive', {}).get('corrected_note', '')
                
                korean_grade = evaluation_result.get('grade', '평균')
                evaluation_result['grade_code'] = korean_grade
                evaluation_result['corrected_note'] = corrected_note
            else:
                korean_grade = '평가없음'
                evaluation_result = self.create_empty_evaluation()
        else:
            # NURSING, RECOVERY는 기본 평가
            korean_grade = '평균'
            evaluation_result = {
                'oer_fidelity': 'O',
                'specificity': 'O',
                'grammar': 'O',
                'grade': '평균',
                'grade_code': '평균'
            }
        
        self.save_ai_evaluation(record_id, category, note_writer_user_id, evaluation_result, note_text)
        
        return {
            'grade_code': korean_grade,
            'evaluation': evaluation_result
        }


# 서비스 인스턴스 생성
evaluation_service = EvaluationService()
