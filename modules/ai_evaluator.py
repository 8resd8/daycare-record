import streamlit as st
from openai import OpenAI
import json

class AIEvaluator:
    def __init__(self):
        try:
            # streamlit secrets에서 API 키를 가져옵니다.
            self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        except Exception as e:
            st.error(f"OpenAI 클라이언트 초기화 오류: {e}")
            self.client = None

    def evaluate_daily_record(self, record):
        if not self.client:
            return None

        # 프롬프트 디자인: 영역별로 다른 평가 기준을 명확히 제시
        prompt = f"""
        당신은 주간보호센터 요양 기록을 감수하고 품질을 높이는 AI 전문가입니다.
        아래 입력된 기록을 분석하여 영역별로 평가하고, 필요하다면 더 나은 문장으로 수정해 주세요.

        [입력 데이터]
        - 날짜: {record.get('date', '날짜 없음')}
        - 신체활동(physical): {record.get('physical_note', '')}
        - 인지관리(cognitive): {record.get('cognitive_note', '')}
        - 간호관리(nursing): {record.get('nursing_note', '')}
        - 기능회복(recovery): {record.get('functional_note', '')}

        [공통 작성 지침]
        - 말투: 모든 'revised_sentence(수정 제안)'는 반드시 '~했음', '~하심', '~함' 등의 명사형 종결 말투를 사용하세요. (예: 식사를 잘 하심, 프로그램에 적극 참여함)
        - revised_sentence: 부연 설명 없이 수정된 문장만 출력하세요.

        [평가 기준 및 수정 가이드]

        1. 신체활동 / 인지관리 영역
           - 우수: '상황(언제/어디서) -> 관찰(무엇을) -> 조치/반응(어떻게 했다)'의 육하원칙 구조가 명확함.
           - 평균: 의미는 통하지만 구체적인 상황이나 조치가 다소 부족하거나 문장이 평범함.
           - 개선: 내용이 없거나, 너무 짧거나, 문맥이 이상하여 전면 수정이 필요함.
           - 수정 목표: '상황-관찰-조치' 구조를 갖추도록 내용을 보강하여 작성.

        2. **간호관리(nursing) / 기능회복(recovery)** 영역
           - 우수: 어르신의 관찰 내용, 행동, 건강 상태가 구체적이고 문장의 흐름이 자연스러움.
           - 평균: 의미는 통하지만 구체성(수치, 정확한 상태 등)이 부족하거나 문장이 다소 어색함.
           - 개선: 정보가 너무 모호하거나, 오타/파싱 오류로 인해 이해가 어려워 수정이 필요함.
           - 수정 목표: 구체적인 상태를 명시하고 자연스러운 흐름으로 다듬어 작성.

        [JSON 출력 형식]
        응답은 반드시 아래 JSON 포맷으로만 출력해야 합니다.
        {{
          "date": "{record.get('date')}",
          "physical": {{"grade": "우수|평균|개선", "revised_sentence": "수정된 문장", "reason": "평가 이유", "original_sentence": "{record.get('physical_note', '')}"}},
          "cognitive": {{"grade": "우수|평균|개선", "revised_sentence": "수정된 문장", "reason": "평가 이유", "original_sentence": "{record.get('cognitive_note', '')}"}},
          "nursing": {{"grade": "우수|평균|개선", "revised_sentence": "수정된 문장", "reason": "평가 이유", "original_sentence": "{record.get('nursing_note', '')}"}},
          "recovery": {{"grade": "우수|평균|개선", "revised_sentence": "수정된 문장", "reason": "평가 이유", "original_sentence": "{record.get('functional_note', '')}"}}
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # JSON 처리에 강한 최신 모델 권장 (gpt-4o 또는 gpt-4o-mini)
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs strictly in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"AI 평가 중 오류 발생: {e}")
            return None