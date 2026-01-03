"""AI 평가 서비스 - 일일 기록 평가 비즈니스 로직"""

import json
import re
from typing import Dict, Optional, Any, List
from modules.clients.daily_prompt import get_special_note_prompt
from modules.repositories import AiEvaluationRepository
from modules.clients.ai_client import get_ai_client
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class EvaluationService:
    """AI 평가 서비스 클래스"""
    
    def __init__(self):
        self.ai_eval_repo = AiEvaluationRepository()
    
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
            ai_client = get_ai_client()
        except Exception as e:
            print(f'AI 클라이언트 초기화 오류: {e}')
            return None
        
        system_prompt, user_prompt = get_special_note_prompt(record)
        
        try:
            response = ai_client.chat_completion(
                model='gpt-4o-mini',
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
                           vectorizer: TfidfVectorizer) -> str:
        """후보 중에서 참조 문장들과 가장 유사도가 낮은 문장 찾기"""
        if not references:
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
