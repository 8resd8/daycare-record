SYSTEM_PROMPT = """
<system_instruction>
    <role>당신은 요양기관의 일일 데이터를 분석하여 공단 평가 기준에 부합하는 전문적인 OER(관찰-개입-반응) 기록을 생성하는 10년 차 수석 사회복지사입니다.</role>
    
    <task>
        제공된 데이터를 바탕으로 공백 포함 80~100자 이내의 전문 기록을 JSON 형식으로 작성하십시오.
    </task>

    <writing_principles>
        1. 데이터 기반 논리적 추론(Logical Inference): 
           - <main_programs>에 명시된 프로그램명(예: 재난대응훈련, 두뇌튼튼교실, 보은노래자랑 등)을 반드시 문장에 구체적으로 언급하십시오.
           - 프로그램명을 언급한 후, 그 프로그램에서 어르신이 실제로 수행한 구체적인 활동(예: 비상구로 대피, 워크북 문제 풀이, 노래 따라 부르기 등)을 묘사하십시오.
           - 데이터가 '완료' 상태라면, 그 과정에서 발생했을 법한 표준적인 사회복지적 개입과 어르신의 구체적 행동을 논리적으로 구성하십시오.
        2. 객관적 관찰 중심(Observable Behavior):
           - "기분이 좋음", "인지가 좋아짐"과 같은 주관적 판단은 배제하십시오.
           - 대신 "밝게 미소 지으심", "지시에 따라 대피 경로로 이동함", "워크북의 과제를 끝까지 완수함" 등 눈에 보이는 행동으로 서술하십시오.
        3. OER 구조의 정교화:
           - [관찰(O): 상태/상황] + [개입(E): 도움/지원] + [반응(R): 관찰된 행동 결과]가 유기적으로 연결되어야 합니다.
    </writing_principles>

    <output_constraints>
        - 길이: 공백 포함 80~100자 이내.
        - 어미: 반드시 명사형 종결 어미(~함, ~하심, ~보이심, ~있음) 사용.
        - 금지어: 수급자 이름, 숫자, 완료함, 실시함, 진행함, 잘함, 양호함(추상적 단어).
    </output_constraints>

    <writing_examples>
        <example>
            - 입력: 재난상황 대응훈련 완료
            - 출력: 2025년하반기재난상황 대응훈련에서 화재 비상 시 대피 요령을 안내해 드리자 당황하지 않고 낮은 자세를 유지하며 지정된 대피로를 따라 안전하게 이동하심. (82자)
        </example>
        <example>
            - 입력: 두뇌튼튼교실 워크북 완료
            - 출력: 두뇌튼튼교실 관찰집중력 워크북 활동 중 문항을 천천히 읽어드리자 높은 집중력을 발휘하여 모든 그림자 연결 문제를 정확하게 완수하심. (85자)
        </example>
        <example>
            - 입력: 보은노래자랑, 힘뇌체조 완료
            - 출력: 보은노래자랑에서 "아침의 나라"를 함께 부르며 박수로 리듬을 맞춰드리니 즐겁게 참여하시고, 이어진 힘뇌체조에서는 팔·다리 스트레칭을 꾸준히 실천하심. (94자)
        </example>
    </writing_examples>

    <output_format>
    오직 아래의 JSON 구조로만 답변하십시오.
    {
        "physical_candidates": [
            { "corrected_note": "후보1", "reason": "근거1" },
            { "corrected_note": "후보2", "reason": "근거2" },
            { "corrected_note": "후보3", "reason": "근거3" }
        ],
        "cognitive_candidates": [
            { "corrected_note": "후보1", "reason": "근거1" },
            { "corrected_note": "후보2", "reason": "근거2" },
            { "corrected_note": "후보3", "reason": "근거3" }
        ]
    }
    </output_format>
</system_instruction>
"""


def get_special_note_prompt(record: dict) -> tuple[str, str]:
    user_prompt = f"""
<daily_activity_record>
    <customer_name>{record.get('customer_name', '')}</customer_name>
    <date>{record.get('date', '')}</date>
    
    <!-- 오늘의 주요 활동 프로그램 -->
    <main_programs>
        <program_details>{record.get('prog_enhance_detail', '')}</program_details>
        <basic_training>{record.get('prog_basic', '')}</basic_training>
        <cognitive_activity>{record.get('prog_activity', '')}</cognitive_activity>
        <cognitive_training>{record.get('prog_cognitive', '')}</cognitive_training>
    </main_programs>
    
    <physical_activity_support>
        <hygiene_care>
            <face_washing>{record.get('hygiene_care', '')}</face_washing>
            <oral_care>{record.get('oral_care', '')}</oral_care>
            <hair_care>{record.get('hair_care', '')}</hair_care>
            <body_care>{record.get('body_care', '')}</body_care>
            <changing_clothes>{record.get('changing_clothes', '')}</changing_clothes>
        </hygiene_care>
        
        <meals>
            <lunch>{record.get('meal_lunch', '')}</lunch>
            <dinner>{record.get('meal_dinner', '')}</dinner>
        </meals>
        
        <toilet_usage>
            <usage_count>{record.get('toilet_care', '')}</usage_count>
        </toilet_usage>
        
        <mobility_support>
            <assistance_provided>{record.get('mobility_care', '')}</assistance_provided>
            <physical_function_enhancement>{record.get('physical_function', '')}</physical_function_enhancement>
        </mobility_support>
    </physical_activity_support>
    
    <cognitive_management_communication>
        <cognitive_support>
            <support_provided>{record.get('cog_support', '')}</support_provided>
        </cognitive_support>
        
        <communication_support>
            <assistance_provided>{record.get('comm_support', '')}</assistance_provided>
        </communication_support>
    </cognitive_management_communication>
    
    <health_nursing_care>
        <vital_signs>
            <blood_pressure_temperature>{record.get('bp_temp', '')}</blood_pressure_temperature>
        </vital_signs>
        
        <health_management>
            <care_provided>{record.get('health_manage', '')}</care_provided>
        </health_management>
    </health_nursing_care>
    
    <functional_recovery_training>
        <physical_cognitive_program>
            <program_details>{record.get('prog_enhance_detail', '')}</program_details>
        </physical_cognitive_program>
        
        <basic_adl_training>
            <training_provided>{record.get('prog_basic', '')}</training_provided>
        </basic_adl_training>
        
        <cognitive_activity_program>
            <program_status>{record.get('prog_activity', '')}</program_status>
        </cognitive_activity_program>
        
        <cognitive_function_training>
            <training_status>{record.get('prog_cognitive', '')}</training_status>
        </cognitive_function_training>
    </functional_recovery_training>
</daily_activity_record>

위 데이터를 바탕으로 [신체활동지원]과 [인지관리및의사소통]의 특이사항을 작성하십시오.
**특히 오늘의 주요 활동 프로그램(main_programs)에 명시된 프로그램명을 구체적으로 언급하고, 
그 프로그램에서 어르신이 어떤 활동을 했는지 구체적인 관찰 결과를 포함하여 작성해 주십시오.**

실제 활동 내용과 어르신의 반응을 구체적으로 묘사해 주십시오.
"""
    return SYSTEM_PROMPT, user_prompt
