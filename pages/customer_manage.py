import pandas as pd
import streamlit as st
import mysql.connector
from datetime import date

# 모듈 import
from modules.customers import create_customer, delete_customer, list_customers, update_customer
from modules.analytics import inject_clarity_tracking

# --- 페이지 설정 ---
st.set_page_config(page_title="수급자 관리", layout="wide", page_icon="👥")

# Microsoft Clarity
inject_clarity_tracking()

# --- 스타일링 ---
st.markdown("""
<style>
    .stDeployButton {display:none;}
    h1 { margin-bottom: 2rem; }
    [data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    nav = st.radio(
        "메뉴",
        options=["파일 처리", "수급자 관리", "대시보드"],
        index=1,
        horizontal=True,
        key="sidebar_nav_customers",
    )
    if nav == "파일 처리":
        st.switch_page("app.py")
    elif nav == "대시보드":
        st.switch_page("pages/dashboard.py")


# --- 메인 로직 ---

st.title("👥 수급자 통합 관리")

# 1. 검색 및 필터 영역
with st.container():
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        search_keyword = st.text_input("🔍 검색 (이름 또는 인정번호)", placeholder="검색어를 입력하세요...")
    with col2:
        st.write("")
        refresh = st.button("🔄 새로고침", use_container_width=True)

# 2. 데이터 로드
try:
    customers_data = list_customers(keyword=search_keyword.strip() or None)
except mysql.connector.Error:
    st.stop()

# Pandas DataFrame으로 변환
df = pd.DataFrame(customers_data)

if df.empty:
    df = pd.DataFrame(columns=["customer_id", "name", "birth_date", "gender", "recognition_no", "benefit_start_date", "grade"])

# [중요] 날짜 컬럼을 Pandas의 datetime 객체로 확실하게 변환
df["birth_date"] = pd.to_datetime(df["birth_date"], errors='coerce')
df["benefit_start_date"] = pd.to_datetime(df["benefit_start_date"], errors='coerce')

# 3. 데이터 에디터 설정
column_config = {
    "customer_id": st.column_config.NumberColumn(
        "ID",
        disabled=True,
        format="%d"
    ),
    "name": st.column_config.TextColumn(
        "수급자 명",
        required=True
    ),
    "birth_date": st.column_config.DateColumn(
        "생년월일",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
        format="YYYY-MM-DD",
    ),
    "gender": st.column_config.SelectboxColumn(
        "성별",
        options=["남성", "여성"],
        required=True
    ),
    "recognition_no": st.column_config.TextColumn(
        "인정번호",
        width="medium"
    ),
    "benefit_start_date": st.column_config.DateColumn(
        "급여개시일",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
        format="YYYY-MM-DD",
    ),
    "grade": st.column_config.SelectboxColumn(
        "등급",
        options=["1등급", "2등급", "3등급", "4등급", "5등급", "인지지원등급"],
    )
}

st.info("💡 표의 내용을 수정하거나 맨 아래 행에 추가한 뒤 [변경사항 저장]을 눌러주세요.")

edited_df = st.data_editor(
    df,
    column_config=column_config,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    key="customer_editor"
)

# 4. 저장 로직
if st.button("💾 변경사항 저장", type="primary", use_container_width=True):
    try:
        # [핵심] 모든 입력값에 대해 리스트/NaN/NaT를 처리하는 강력한 클리닝 함수
        def clean_input(val):
            # 1. 리스트인 경우 첫 번째 값 추출
            if isinstance(val, list):
                val = val[0] if len(val) > 0 else None

            # 2. Pandas 날짜 타입(Timestamp)인 경우 Python date 객체로 변환
            if isinstance(val, pd.Timestamp):
                return val.date()

            # 3. 빈 값(NaN, None, "") 처리
            if pd.isna(val) or val == "":
                return None

            return val

        original_ids = set(df["customer_id"].dropna())
        current_ids = set(edited_df["customer_id"].dropna())
        deleted_ids = original_ids - current_ids

        changes_log = {"added": 0, "updated": 0, "deleted": 0}

        with st.status("데이터베이스 동기화 중...", expanded=True) as status:

            # (1) 삭제
            if deleted_ids:
                status.write(f"🗑️ {len(deleted_ids)}건 삭제 중...")
                for d_id in deleted_ids:
                    delete_customer(int(d_id))
                changes_log["deleted"] = len(deleted_ids)

            # (2) 추가 및 수정
            for index, row in edited_df.iterrows():
                # 모든 필드에 clean_input 적용 (생년월일 오류 방지)
                c_name = clean_input(row.get("name"))

                # 이름이 없으면 저장하지 않음
                if not c_name: continue

                c_birth = clean_input(row.get("birth_date"))
                c_gender = clean_input(row.get("gender"))
                c_rec_no = clean_input(row.get("recognition_no"))
                c_start = clean_input(row.get("benefit_start_date"))
                c_grade = clean_input(row.get("grade"))

                # 신규 등록
                if pd.isna(row.get("customer_id")):
                    create_customer(
                        name=c_name,
                        birth_date=c_birth,
                        gender=c_gender,
                        recognition_no=c_rec_no,
                        benefit_start_date=c_start,
                        grade=c_grade
                    )
                    changes_log["added"] += 1

                # 수정
                elif row["customer_id"] in current_ids:
                    update_customer(
                        customer_id=int(row["customer_id"]),
                        name=c_name,
                        birth_date=c_birth,
                        gender=c_gender,
                        recognition_no=c_rec_no,
                        benefit_start_date=c_start,
                        grade=c_grade
                    )
                    changes_log["updated"] += 1

            status.update(label="✅ 저장 완료!", state="complete", expanded=False)

        msg = []
        if changes_log['added']: msg.append(f"{changes_log['added']}건 추가")
        if changes_log['updated']: msg.append(f"{changes_log['updated']}건 수정")
        if changes_log['deleted']: msg.append(f"{changes_log['deleted']}건 삭제")

        if msg:
            st.success(f"처리 결과: {', '.join(msg)}")
            import time
            time.sleep(1)
            st.rerun()
        else:
            st.info("변경 사항이 없습니다.")

    except Exception as e:
        # 디버깅을 위해 상세 에러 표시
        st.error(f"저장 중 오류 발생: {str(e)}")
        st.write("오류 상세:", e)