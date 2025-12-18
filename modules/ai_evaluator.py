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
        당신은 요양보호 기록(주간보호센터) 특이사항 문장 품질을 개선하는 전문가입니다.

        [입력]
        - 날짜: {record['date']}
        - 신체 특이사항: {record['physical_note']}
        - 인지 특이사항: {record['cognitive_note']}
        - 간호 특이사항: {record['nursing_note']}
        - 기능 특이사항: {record['functional_note']}

        [평가 기준]
        - PDF 파싱데이터 특성상 띄어쓰기/개행이 불안정할 수 있음.
        - 다음 중 하나면 '개선필요'로 판단:
          1) 내용이 너무 짧거나 모호함(예: "특이사항 없음" 수준)
          2) 관찰/행동/상태가 구체적으로 드러나지 않음
          3) 문장이 어색하거나 파싱 오류로 읽기 어려움
        - 개선이 필요하지 않으면 해당 영역은 null 로 출력.
        - 개선이 필요하면 아래 필드를 모두 채움.
        - **중요**: `suggested_sentence`에는 설명/사족 없이 "수정된 문장"만 출력.

        [JSON 출력 형식]
        {{
          "date": "YYYY-MM-DD",
          "physical": {{"suggested_sentence": "", "reason": "", "original_sentence": ""}} | null,
          "cognitive": {{"suggested_sentence": "", "reason": "", "original_sentence": ""}} | null,
          "nursing": {{"suggested_sentence": "", "reason": "", "original_sentence": ""}} | null,
          "recovery": {{"suggested_sentence": "", "reason": "", "original_sentence": ""}} | null
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