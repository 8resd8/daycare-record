import streamlit as st
import pandas as pd
import time

# 모듈 import (modules 폴더가 있어야 함)
from modules.parser import CareRecordParser
from modules.database import save_parsed_data
from modules.ai_evaluator import AIEvaluator

# --- 페이지 설정 ---
st.set_page_config(page_title="요양기록 AI 매니저", layout="wide", page_icon="🏥")
st.title("🏥 주간보호센터 기록 관리 시스템")

# --- 세션 상태 초기화 ---
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = []
if "eval_results" not in st.session_state:
    st.session_state.eval_results = {}
if "ai_suggestion_tables" not in st.session_state:
    st.session_state.ai_suggestion_tables = {}

# --- 사이드바: 파일 업로드 ---
with st.sidebar:
    st.header("📂 파일 처리")
    uploaded_file = st.file_uploader("PDF 기록지 업로드", type=["pdf"])

    if uploaded_file:
        if not st.session_state.parsed_data:
            with st.spinner("PDF 정밀 분석 중..."):
                parser = CareRecordParser(uploaded_file)
                st.session_state.parsed_data = parser.parse()
                st.success(f"분석 완료! ({len(st.session_state.parsed_data)}일치)")

        if st.button("🔄 다른 파일 올리기 (초기화)"):
            st.session_state.parsed_data = []
            st.session_state.eval_results = {}
            st.rerun()

# --- 메인 화면 구성 ---
# 크게 두 개의 탭으로 나눕니다.
main_tab1, main_tab2 = st.tabs(["📄 기록 조회 및 DB 저장", "🤖 AI 품질 평가"])

# =========================================================
# [탭 1] 기록 상세 조회 및 DB 저장
# =========================================================
with main_tab1:
    if not st.session_state.parsed_data:
        st.info("👈 왼쪽 사이드바에서 PDF 파일을 업로드해주세요.")
    else:
        data = st.session_state.parsed_data
        customer_name = data[0]['customer_name']
        st.markdown(f"### 👤 대상자: **{customer_name}** 어르신")

        evaluator = AIEvaluator()

        # --- 여기서 4가지 상세 탭을 보여줍니다 ---
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "💪 신체활동지원", "🧠 인지관리", "🩺 간호관리", "🏃 기능회복"
        ])

        # 1. 신체활동 탭
        with sub_tab1:
            df_phy = pd.DataFrame([{
                "날짜": r['date'],
                "특이사항": r['physical_note'],
                "세면/구강": r['hygiene_care'],
                "목욕": r['bath_time'] if r['bath_time'] == "없음" else f"{r['bath_time']} / {r['bath_method']}",
                "식사(아/점/저)": f"{r['meal_breakfast']} / {r['meal_lunch']} / {r['meal_dinner']}",
                "화장실": r['toilet_care'],
                "이동도움": r['mobility_care'],
                "작성자": r['writer_phy']
            } for r in data])
            st.dataframe(df_phy, use_container_width=True, hide_index=True)


            if st.session_state.ai_suggestion_tables.get("physical") is not None and "physical" in st.session_state.ai_suggestion_tables:
                st.divider()
                rows = st.session_state.ai_suggestion_tables.get("physical", [])
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.info("신체 특이사항에서 개선이 필요한 항목이 발견되지 않았습니다.")

        # 2. 인지관리 탭
        with sub_tab2:
            df_cog = pd.DataFrame([{
                "날짜": r['date'],
                "특이사항": r['cognitive_note'],
                "인지관리지원": r['cog_support'],
                "의사소통도움": r['comm_support'],
                "작성자": r['writer_cog']
            } for r in data])
            st.dataframe(df_cog, use_container_width=True, hide_index=True)


            if st.session_state.ai_suggestion_tables.get("cognitive") is not None and "cognitive" in st.session_state.ai_suggestion_tables:
                st.divider()
                rows = st.session_state.ai_suggestion_tables.get("cognitive", [])
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.info("인지 특이사항에서 개선이 필요한 항목이 발견되지 않았습니다.")

        # 3. 간호관리 탭
        with sub_tab3:
            df_nur = pd.DataFrame([{
                "날짜": r['date'],
                "특이사항": r['nursing_note'],
                "혈압/체온": r['bp_temp'],
                "건강관리": r['health_manage'],
                "간호관리": r['nursing_manage'],
                "응급서비스": r['emergency'],
                "작성자": r['writer_nur']
            } for r in data])
            st.dataframe(df_nur, use_container_width=True, hide_index=True)


            if st.session_state.ai_suggestion_tables.get("nursing") is not None and "nursing" in st.session_state.ai_suggestion_tables:
                st.divider()
                rows = st.session_state.ai_suggestion_tables.get("nursing", [])
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.info("간호 특이사항에서 개선이 필요한 항목이 발견되지 않았습니다.")

        # 4. 기능회복 탭
        with sub_tab4:
            df_func = pd.DataFrame([{
                "날짜": r['date'],
                "특이사항": r['functional_note'],
                "기본동작": r['prog_basic'],
                "인지활동": r['prog_activity'],
                "인지기능": r['prog_cognitive'],
                "물리치료": r['prog_therapy'],
                "작성자": r['writer_func']
            } for r in data])
            st.dataframe(df_func, use_container_width=True, hide_index=True)

            if st.session_state.ai_suggestion_tables.get("recovery") is not None and "recovery" in st.session_state.ai_suggestion_tables:
                st.divider()
                rows = st.session_state.ai_suggestion_tables.get("recovery", [])
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.info("기능 특이사항에서 개선이 필요한 항목이 발견되지 않았습니다.")

        st.divider()

        # DB 저장 버튼
        if st.button("💾 데이터베이스에 저장하기", type="primary"):
            with st.spinner("DB 저장 중..."):
                count = save_parsed_data(data)
                if count > 0:
                    st.toast(f"✅ {count}건의 기록이 안전하게 저장되었습니다!", icon="💾")
                else:
                    st.error("저장에 실패했습니다. 로그를 확인해주세요.")

# =========================================================
# [탭 2] AI 품질 평가
# =========================================================
with main_tab2:
    if not st.session_state.parsed_data:
        st.warning("먼저 PDF를 업로드해야 평가할 수 있습니다.")
    else:
        st.markdown("### 📊 기록 품질 전수 조사 (AI Review)")
        st.info("모든 날짜의 기록을 4가지 영역(신체, 인지, 간호, 기능)으로 나누어 개선이 필요한 문장을 추출합니다.")

        # 평가 시작 버튼
        if st.button("🚀 전체 평가 시작 (Start Evaluation)"):
            evaluator = AIEvaluator()
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(st.session_state.parsed_data)

            for i, record in enumerate(st.session_state.parsed_data):
                status_text.text(f"분석 중... ({record['date']})")

                # AI 평가 실행 (Modules 호출)
                result = evaluator.evaluate_daily_record(record)
                if result:
                    st.session_state.eval_results[record['date']] = result

                # 진행률 업데이트
                progress_bar.progress((i + 1) / total)
                time.sleep(0.1) # API 요청 속도 조절

            status_text.text("분석 완료!")
            st.success("모든 평가가 완료되었습니다!")

        # --- 평가 결과 시각화 ---
        if st.session_state.eval_results:
            st.divider()

            rows = []
            for date, res in st.session_state.eval_results.items():
                for label, key, original_key in [
                    ("신체", "physical", "physical_note"),
                    ("인지", "cognitive", "cognitive_note"),
                    ("간호", "nursing", "nursing_note"),
                    ("기능", "recovery", "functional_note"),
                ]:
                    item = (res or {}).get(key)
                    if item:
                        rows.append({
                            "날짜": date,
                            "영역": label,
                            "특이사항 수정 문장": item.get("suggested_sentence", ""),
                            "기존문장": item.get("original_sentence", ""),
                            "이유": item.get("reason", ""),
                        })

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("개선이 필요한 항목이 발견되지 않았습니다.")