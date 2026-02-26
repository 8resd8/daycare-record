import pandas as pd
import streamlit as st
from datetime import date

from modules.analytics import inject_clarity_tracking
from modules.repositories import UserRepository

# --- 페이지 설정 ---
st.set_page_config(page_title="직원 관리", layout="wide", page_icon="👤")

# Microsoft Clarity
inject_clarity_tracking()

# --- 스타일링 ---
st.markdown(
    """
<style>
    .stDeployButton {display:none;}
    h1 { margin-bottom: 2rem; }
    [data-testid="stSidebarNav"] { display: none; }
</style>
""",
    unsafe_allow_html=True,
)

# --- 사이드바 네비게이션 ---
with st.sidebar:
    nav = st.radio(
        "메뉴",
        options=["파일 처리", "수급자 관리", "직원 관리", "대시보드"],
        index=2,
        horizontal=True,
        key="sidebar_nav_employees",
    )
    if nav == "파일 처리":
        st.switch_page("app.py")
    elif nav == "수급자 관리":
        st.switch_page("pages/customer_manage.py")
    elif nav == "대시보드":
        st.switch_page("pages/dashboard.py")

# --- 메인 로직 ---
st.title("직원 관리")
user_repo = UserRepository()

# 1) 검색 및 필터
with st.container():
    col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
    with col1:
        search_keyword = st.text_input("", placeholder="검색어 입력 후 엔터 (이름/아이디/직종)")
    with col2:
        work_status_filter = st.selectbox("근무상태", ["전체", "재직", "휴직", "퇴사"], index=0)


# 2) 데이터 로드
def load_users():
    try:
        data = user_repo.list_users(
                keyword=search_keyword.strip() or None,
                work_status=work_status_filter,
            )
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

users_df = load_users()
if users_df.empty:
    users_df = pd.DataFrame(
        columns=[
            "user_id",
            "name",
            "gender",
            "birth_date",
            "work_status",
            "job_type",
            "hire_date",
            "resignation_date",
            "license_name",
            "license_date",
            "created_at",
        ]
    )

# 원본 백업
original_df = users_df.copy()

# 3) 컬럼 설정 (user_id, password, role, updated_at 제외)
column_config = {
    "user_id": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
    "username": None,  # 로그인 아이디는 숨김
    "name": st.column_config.TextColumn("직원명", required=True, max_chars=50),
    "gender": st.column_config.SelectboxColumn("성별", options=["남성", "여성"], required=False),
    "birth_date": st.column_config.DateColumn(
        "생년월일", min_value=date(1950, 1, 1), max_value=date.today(), format="YYYY-MM-DD"
    ),
    "work_status": st.column_config.SelectboxColumn(
        "근무 현황", options=["재직", "휴직", "퇴사"], default="재직", required=True
    ),
    "job_type": st.column_config.TextColumn("담당 직종", help="예: 요양보호사, 사회복지사 등", max_chars=50),
    "hire_date": st.column_config.DateColumn(
        "입사일", min_value=date(2000, 1, 1), max_value=date.today(), format="YYYY-MM-DD"
    ),
    "resignation_date": st.column_config.DateColumn(
        "퇴사일", min_value=date(2000, 1, 1), max_value=date.today(), format="YYYY-MM-DD"
    ),
    "license_name": st.column_config.TextColumn("자격증 명칭", max_chars=100),
    "license_date": st.column_config.DateColumn(
        "자격증 발급일", min_value=date(1950, 1, 1), max_value=date.today(), format="YYYY-MM-DD"
    ),
    "created_at": st.column_config.DatetimeColumn("등록일", disabled=True, format="YYYY-MM-DD HH:mm:ss"),
}

# 4) 데이터 편집기
st.subheader("📋 직원 목록")
edited_df = st.data_editor(
    users_df,
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="employee_editor",
)

# 5) 저장 처리 헬퍼
DEFAULT_TEMP_PASSWORD = "Temp@1234"  # TODO: 운영 시 암호화/변경 필요


def _to_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    return val


def save_changes():
    try:
        added = []
        updated = []
        deleted = []

        # ID 세트
        original_ids = set(original_df["user_id"].dropna().astype(int)) if not original_df.empty else set()
        current_ids = set(edited_df["user_id"].dropna().astype(int)) if not edited_df.empty else set()

        # 삭제 -> 퇴사 처리
        for del_id in original_ids - current_ids:
            user_repo.soft_delete_user(int(del_id))
            deleted.append(del_id)

        # 추가 및 수정 처리
        for _, row in edited_df.iterrows():
            uid = row.get("user_id")
            name = str(row.get("name") or "").strip()
            if not name:
                continue

            # username 자동 생성 (name + timestamp 기반)
            import time
            timestamp = int(time.time())
            username = f"user_{name}_{timestamp}"

            payload = {
                "name": name,
                "gender": row.get("gender"),
                "birth_date": _to_date(row.get("birth_date")),
                "work_status": row.get("work_status") or "재직",
                "job_type": row.get("job_type"),
                "hire_date": _to_date(row.get("hire_date")),
                "resignation_date": _to_date(row.get("resignation_date")),
                "license_name": row.get("license_name"),
                "license_date": _to_date(row.get("license_date")),
            }

            if pd.isna(uid) or uid is None:
                user_repo.create_user(
                    username=username,
                    password=DEFAULT_TEMP_PASSWORD,
                    name=name,
                    gender=payload["gender"],
                    birth_date=payload["birth_date"],
                    work_status=payload["work_status"],
                    job_type=payload["job_type"],
                    hire_date=payload["hire_date"],
                    resignation_date=payload["resignation_date"],
                    license_name=payload["license_name"],
                    license_date=payload["license_date"],
                )
                added.append(name)
            else:
                orig_row = original_df[original_df["user_id"] == uid]
                if not orig_row.empty:
                    # 변경 여부 체크
                    changed = False
                    for k in payload:
                        ov = orig_row.iloc[0].get(k)
                        nv = payload[k]
                        if pd.isna(ov):
                            ov = None
                        if pd.isna(nv):
                            nv = None
                        if ov != nv:
                            changed = True
                            break
                    if changed:
                        user_repo.update_user(user_id=int(uid), **payload)
                        updated.append(uid)

        return True, added, updated, deleted
    except Exception as e:
        return False, str(e)


# 6) 저장 버튼
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("💾 변경사항 저장", type="primary", use_container_width=True):
        result = save_changes()
        if result[0] is True:
            added, updated, deleted = result[1], result[2], result[3]
            msg_parts = []
            if added:
                msg_parts.append(f"{len(added)}건 추가")
            if updated:
                msg_parts.append(f"{len(updated)}건 수정")
            if deleted:
                msg_parts.append(f"{len(deleted)}건 퇴사 처리")
            toast_msg = "저장 완료" + (": " + ", ".join(msg_parts) if msg_parts else " (변경 없음)")
            st.toast(toast_msg, icon="✅")
            st.rerun()
        else:
            st.error(f"저장 중 오류: {result[1]}")

# 7) 통계 요약
if not users_df.empty:
    st.markdown("---")
    st.subheader("📊 통계 정보")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("전체 인원", f"{len(users_df)}명")
    with col_b:
        st.metric("재직", f"{len(users_df[users_df['work_status'] == '재직'])}명")
    with col_c:
        st.metric("휴직", f"{len(users_df[users_df['work_status'] == '휴직'])}명")
    with col_d:
        st.metric("퇴사", f"{len(users_df[users_df['work_status'] == '퇴사'])}명")
