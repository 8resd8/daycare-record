import streamlit as st
from openai import OpenAI
import json

class AIEvaluator:
    def __init__(self):
        try:
            self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        except:
            self.client = None

    def evaluate_daily_record(self, record):
        if not self.client: return None

        prompt = f"""
        당신은 주간보호센터 특이사항 문장 품질을 평가/개선하는 전문가입니다.

        [입력]
        - 날짜: {record['date']}
        - 신체 특이사항: {record['physical_note']}
        - 인지 특이사항: {record['cognitive_note']}
        - 간호 특이사항: {record['nursing_note']}
        - 기능 특이사항: {record['functional_note']}

        [평가 기준]
        - 각 활동(신체/인지/간호/기능)별 특이사항이 "잘 완성"되었는지 평가.
        - PDF 파싱데이터 특성상 띄어쓰기/개행이 불안정할 수 있음.
        - 등급은 아래 3개 중 하나로만 출력:
          - 우수: 관찰/행동/상태가 구체적이고 자연스러움
          - 평균: 의미는 통하지만 구체성이 부족하거나 문장이 다소 어색함(큰 수정은 불필요)
          - 개선: 문장이 너무 짧거나 모호/어색/파싱오류로 품질이 낮아 수정이 필요
        - **중요**: 등급이 "개선"일 때만 `revised_sentence`에 수정 특이사항 문장을 출력하고,
          "우수"/"평균"이면 `revised_sentence`는 빈 문자열로 출력.
        - `revised_sentence`에는 설명/사족 없이 "수정된 문장"만 출력.

        [JSON 출력 형식]
        {{
          "date": "YYYY-MM-DD",
          "physical": {{"grade": "우수|평균|개선", "revised_sentence": "", "reason": "", "original_sentence": ""}},
          "cognitive": {{"grade": "우수|평균|개선", "revised_sentence": "", "reason": "", "original_sentence": ""}},
          "nursing": {{"grade": "우수|평균|개선", "revised_sentence": "", "reason": "", "original_sentence": ""}},
          "recovery": {{"grade": "우수|평균|개선", "revised_sentence": "", "reason": "", "original_sentence": ""}}
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "system", "content": "JSON output only."},
                          {"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return None