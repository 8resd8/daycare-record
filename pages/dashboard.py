"""📊 대시보드 - 직원 관리 현황 (개편)"""

import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from modules.db_connection import get_db_connection

# --- 페이지 설정 ---
st.set_page_config(page_title="대시보드", layout="wide", page_icon="📊")

# --- 스타일링 ---
st.markdown("""
<style>
    .stDeployButton {display:none;}
    h1 { margin-bottom: 1rem; }
    [data-testid="stSidebarNav"] { display: none; }
    
    /* KPI 카드 스타일 */
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #666;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 600;
    }
    
    /* 타임라인 스타일 */
    .timeline-item {
        border-left: 3px solid #4CAF50;
        padding-left: 15px;
        margin-bottom: 15px;
    }
    .timeline-date {
        color: #666;
        font-size: 0.85rem;
    }
    .timeline-type {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 로드 함수 ---
@st.cache_data(ttl=300)
def load_dashboard_data(start_date: date, end_date: date) -> dict:
    """대시보드에 필요한 모든 데이터를 한 번에 로드"""
    conn = get_db_connection()
    
    # 1. 직원 평가 데이터 (employee_evaluations)
    emp_eval_query = """
        SELECT 
            ee.emp_eval_id,
            ee.record_id,
            ee.target_date,
            ee.target_user_id,
            ee.evaluator_user_id,
            ee.category,
            ee.evaluation_type,
            ee.score,
            ee.comment,
            ee.evaluation_date,
            ee.created_at,
            u.name AS target_user_name,
            u.work_status
        FROM employee_evaluations ee
        LEFT JOIN users u ON ee.target_user_id = u.user_id
        WHERE ee.evaluation_date BETWEEN %s AND %s
    """
    df_emp_eval = pd.read_sql(emp_eval_query, conn, params=(start_date, end_date))
    
    # 2. AI 평가 데이터 (ai_evaluations)
    ai_eval_query = """
        SELECT 
            ae.ai_eval_id,
            ae.record_id,
            ae.category,
            ae.grade_code,
            ae.oer_fidelity,
            ae.specificity_score,
            ae.grammar_score,
            ae.created_at,
            di.date AS evaluation_date,
            di.customer_id
        FROM ai_evaluations ae
        JOIN daily_infos di ON ae.record_id = di.record_id
        WHERE di.date BETWEEN %s AND %s
    """
    df_ai_eval = pd.read_sql(ai_eval_query, conn, params=(start_date, end_date))
    
    # 3. 재직 중인 직원 목록
    users_query = """
        SELECT user_id, name, work_status
        FROM users
        WHERE work_status = '재직'
        ORDER BY name
    """
    df_users = pd.read_sql(users_query, conn)
    
    # 4. 전월 데이터 (전월 대비 계산용)
    prev_month_start = (datetime.combine(start_date, datetime.min.time()) - relativedelta(months=1)).replace(day=1).date()
    prev_month_end = (datetime.combine(start_date, datetime.min.time()) - timedelta(days=1)).date()
    
    prev_emp_eval_query = """
        SELECT COUNT(*) as count
        FROM employee_evaluations
        WHERE evaluation_date BETWEEN %s AND %s
    """
    df_prev_count = pd.read_sql(prev_emp_eval_query, conn, params=(prev_month_start, prev_month_end))
    
    # 5. 최근 4주 주별 데이터 (Sparkline용)
    four_weeks_ago = end_date - timedelta(weeks=4)
    weekly_query = """
        SELECT 
            u.name AS target_user_name,
            YEARWEEK(ee.evaluation_date, 1) as year_week,
            COUNT(*) as count
        FROM employee_evaluations ee
        LEFT JOIN users u ON ee.target_user_id = u.user_id
        WHERE ee.evaluation_date BETWEEN %s AND %s
        GROUP BY u.name, YEARWEEK(ee.evaluation_date, 1)
        ORDER BY u.name, year_week
    """
    df_weekly = pd.read_sql(weekly_query, conn, params=(four_weeks_ago, end_date))
    
    conn.close()
    
    return {
        "emp_eval": df_emp_eval,
        "ai_eval": df_ai_eval,
        "users": df_users,
        "prev_month_count": df_prev_count['count'].iloc[0] if not df_prev_count.empty else 0,
        "weekly": df_weekly
    }


def get_unique_values(df: pd.DataFrame, column: str) -> list:
    """데이터프레임에서 고유값 목록 추출"""
    if df.empty or column not in df.columns:
        return []
    return sorted(df[column].dropna().unique().tolist())


def create_sparkline(data: list, width: int = 100, height: int = 30) -> str:
    """Sparkline SVG 생성"""
    if not data or len(data) < 2:
        return "—"
    
    max_val = max(data) if max(data) > 0 else 1
    min_val = min(data)
    range_val = max_val - min_val if max_val != min_val else 1
    
    points = []
    step = width / (len(data) - 1)
    for i, val in enumerate(data):
        x = i * step
        y = height - ((val - min_val) / range_val * (height - 4) + 2)
        points.append(f"{x},{y}")
    
    # 추세 색상 (증가: 빨강, 감소: 초록)
    color = "#dc3545" if data[-1] > data[0] else "#28a745"
    
    svg = f'''<svg width="{width}" height="{height}" style="display:inline-block;vertical-align:middle;">
        <polyline fill="none" stroke="{color}" stroke-width="2" points="{' '.join(points)}"/>
    </svg>'''
    return svg


def get_weekly_trend(df_weekly: pd.DataFrame, user_name: str) -> list:
    """특정 직원의 주별 추이 데이터 반환"""
    user_data = df_weekly[df_weekly['target_user_name'] == user_name]
    if user_data.empty:
        return []
    return user_data['count'].tolist()


# --- 사이드바 ---
with st.sidebar:
    # 네비게이션 메뉴
    nav = st.radio(
        "메뉴",
        options=["파일 처리", "수급자 관리", "대시보드"],
        index=2,
        horizontal=True,
        key="sidebar_nav_dashboard",
    )
    if nav == "파일 처리":
        st.switch_page("app.py")
    elif nav == "수급자 관리":
        st.switch_page("pages/customer_manage.py")
    
    st.header("🔍 필터 설정")
    
    # 기간 설정
    st.subheader("📅 기간 설정")
    today = date.today()
    year_start = date(today.year, 1, 1)
    
    date_range = st.date_input(
        "분석 기간",
        value=(year_start, today),
        min_value=date(2020, 1, 1),
        max_value=today,
        key="date_range"
    )
    
    # date_range가 튜플인지 확인
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = year_start, today

# --- 데이터 로드 ---
data = load_dashboard_data(start_date, end_date)
df_emp_eval = data["emp_eval"]
df_ai_eval = data["ai_eval"]
df_users = data["users"]
prev_month_count = data["prev_month_count"]
df_weekly = data["weekly"]

# --- 사이드바 필터 (데이터 로드 후) ---
with st.sidebar:
    st.divider()
    
    # 직원 바로가기 (라디오 버튼)
    st.subheader("👤 직원 선택")
    user_names = df_users['name'].tolist() if not df_users.empty else []
    
    if not df_users.empty:
        selected_user = st.radio(
            "직원 선택",
            options=["전체 보기"] + user_names,
            index=0,
            key="selected_user",
            label_visibility="collapsed"
        )
    else:
        selected_user = "전체 보기"
        st.info("재직 중인 직원이 없습니다.")


# --- 필터 적용 함수 ---
def apply_user_filter(df: pd.DataFrame, user_col: str = 'target_user_name') -> pd.DataFrame:
    """직원 필터 적용"""
    if selected_user != "전체 보기" and user_col in df.columns:
        return df[df[user_col] == selected_user]
    return df.copy()


# 필터 적용
df_emp_filtered = apply_user_filter(df_emp_eval)
df_ai_filtered = df_ai_eval.copy()

# 개별 직원 선택 여부
is_individual_view = selected_user != "전체 보기"

# --- 메인 대시보드 ---
st.title("직원 관리 현황")
st.caption(f"분석 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")

# ============================================
# 탭 구성
# ============================================
tab1, tab2, tab3 = st.tabs(["📊 통계 분석", "📋 직원별 명단", "📝 개별 리포트"])

# ============================================
# 탭 1: 통계 분석 (Bird's Eye View)
# ============================================
with tab1:
    # KPI 카드
    st.subheader("핵심 지표")
    
    col1, col2, col3 = st.columns(3)
    
    # 1. 총 지적 건수
    total_issues = len(df_emp_filtered)
    with col1:
        st.metric(label="총 지적 건수", value=f"{total_issues:,}건")
    
    # 2. 가장 많은 지적 유형
    if not df_emp_filtered.empty:
        top_type = df_emp_filtered['evaluation_type'].value_counts().idxmax()
        top_type_count = df_emp_filtered['evaluation_type'].value_counts().max()
    else:
        top_type = "N/A"
        top_type_count = 0
    with col2:
        st.metric(label="가장 많은 지적 유형", value=f"{top_type}", delta=f"{top_type_count}건")
    
    # 3. 집중 관리 필요 직원 (5건 이상)
    if not df_emp_eval.empty:
        user_counts = df_emp_eval.groupby('target_user_name').size()
        high_risk_count = (user_counts >= 5).sum()
    else:
        high_risk_count = 0
    with col3:
        st.metric(label="집중 관리 필요 (5건↑)", value=f"{high_risk_count}명")
    
    st.markdown("---")
    
    # 평가 분석 실선 그래프
    st.subheader("평가 추이 분석")
    
    # 전체 인원 개수 표시
    total_employees = df_emp_eval['target_user_name'].nunique() if not df_emp_eval.empty else 0
    st.caption(f"전체 평가 대상 인원: {total_employees}명")
    
    if not df_emp_filtered.empty:
        df_trend = df_emp_filtered.copy()
        df_trend['evaluation_date'] = pd.to_datetime(df_trend['evaluation_date'])
        
        # 5개 평가유형별 집계
        eval_types = ['누락', '내용부족', '오타', '문법', '오류']
        
        trend_data = df_trend.groupby(
            [df_trend['evaluation_date'].dt.date, 'evaluation_type']
        ).size().reset_index(name='count')
        trend_data.columns = ['date', 'evaluation_type', 'count']
        trend_data['date'] = pd.to_datetime(trend_data['date'])
        
        # 모든 날짜와 평가유형 조합 생성 (빈 날짜도 0으로 표시)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        all_combinations = pd.MultiIndex.from_product(
            [date_range, eval_types], names=['date', 'evaluation_type']
        ).to_frame(index=False)
        
        trend_data = all_combinations.merge(
            trend_data, on=['date', 'evaluation_type'], how='left'
        ).fillna(0)
        trend_data['count'] = trend_data['count'].astype(int)
        
        # 평가유형별 색상 지정
        type_colors = alt.Scale(
            domain=['누락', '내용부족', '오타', '문법', '오류'],
            range=['#dc3545', '#fd7e14', '#ffc107', '#20c997', '#6f42c1']
        )
        
        # Altair 다중 실선 차트
        line_chart = alt.Chart(trend_data).mark_line(
            strokeWidth=2,
            point=True
        ).encode(
            x=alt.X('date:T', title='날짜', axis=alt.Axis(format='%m/%d')),
            y=alt.Y('count:Q', title='건수'),
            color=alt.Color('evaluation_type:N', title='평가 유형', scale=type_colors),
            tooltip=[
                alt.Tooltip('date:T', title='날짜', format='%Y-%m-%d'),
                alt.Tooltip('evaluation_type:N', title='유형'),
                alt.Tooltip('count:Q', title='건수')
            ]
        ).properties(
            height=300
        ).interactive()
        
        st.altair_chart(line_chart, use_container_width=True)
    else:
        st.info("선택한 기간에 해당하는 평가 데이터가 없습니다.")
    
    st.markdown("---")
    
    # 차트 영역
    chart_col1, chart_col2 = st.columns(2)
    
    # AI 평가 등급 분포 (Donut Chart)
    with chart_col1:
        st.subheader("AI 평가 등급 분포")
        
        if not df_ai_filtered.empty and 'grade_code' in df_ai_filtered.columns:
            grade_counts = df_ai_filtered['grade_code'].value_counts().reset_index()
            grade_counts.columns = ['grade', 'count']
            
            grade_order = ['우수', '평균', '개선', '불량']
            grade_counts['grade'] = pd.Categorical(
                grade_counts['grade'], categories=grade_order, ordered=True
            )
            grade_counts = grade_counts.sort_values('grade')
            
            color_scale = alt.Scale(
                domain=['우수', '평균', '개선', '불량'],
                range=['#28a745', '#17a2b8', '#ffc107', '#dc3545']
            )
            
            donut_chart = alt.Chart(grade_counts).mark_arc(innerRadius=50).encode(
                theta=alt.Theta('count:Q'),
                color=alt.Color('grade:N', title='등급', scale=color_scale),
                tooltip=[
                    alt.Tooltip('grade:N', title='등급'),
                    alt.Tooltip('count:Q', title='건수')
                ]
            ).properties(height=280)
            
            st.altair_chart(donut_chart, use_container_width=True)
        else:
            st.info("AI 평가 데이터가 없습니다.")
    
    # 카테고리별 지적 횟수 (Bar Chart)
    with chart_col2:
        st.subheader("카테고리별 지적 현황")
        
        if not df_emp_filtered.empty and 'category' in df_emp_filtered.columns:
            category_counts = df_emp_filtered['category'].value_counts().reset_index()
            category_counts.columns = ['category', 'count']
            
            bar_chart = alt.Chart(category_counts).mark_bar().encode(
                x=alt.X('category:N', title='카테고리', sort='-y'),
                y=alt.Y('count:Q', title='건수'),
                color=alt.Color('category:N', legend=None, scale=alt.Scale(scheme='blues')),
                tooltip=[
                    alt.Tooltip('category:N', title='카테고리'),
                    alt.Tooltip('count:Q', title='건수')
                ]
            ).properties(height=280)
            
            st.altair_chart(bar_chart, use_container_width=True)
        else:
            st.info("직원 평가 데이터가 없습니다.")

# ============================================
# 탭 2: 직원별 명단 (랭킹 테이블)
# ============================================
with tab2:
    st.subheader("직원별 지적 현황 랭킹")
    
    if not df_emp_eval.empty:
        # 직원별 집계
        employee_summary = df_emp_eval.groupby('target_user_name').agg(
            총_지적_횟수=('emp_eval_id', 'count')
        ).reset_index()
        
        # 주요 유형 (최빈값) 계산
        mode_types = df_emp_eval.groupby('target_user_name')['evaluation_type'].agg(
            lambda x: x.mode().iloc[0] if not x.mode().empty else 'N/A'
        ).reset_index()
        mode_types.columns = ['target_user_name', '주요_유형']
        
        employee_summary = employee_summary.merge(mode_types, on='target_user_name', how='left')
        
        # 정렬 및 순위 추가
        employee_summary = employee_summary.sort_values('총_지적_횟수', ascending=False)
        employee_summary['순위'] = range(1, len(employee_summary) + 1)
        
        # 컬럼 순서 재배치 (4주 추이 제거)
        employee_summary = employee_summary[['순위', 'target_user_name', '총_지적_횟수', '주요_유형']]
        employee_summary.columns = ['순위', '직원명', '지적 횟수', '주요 유형']
        
        # 테이블 표시
        st.dataframe(
            employee_summary,
            column_config={
                "순위": st.column_config.NumberColumn("순위", width="small"),
                "직원명": st.column_config.TextColumn("직원명", width="medium"),
                "지적 횟수": st.column_config.ProgressColumn(
                    "지적 횟수",
                    format="%d건",
                    min_value=0,
                    max_value=int(employee_summary['지적 횟수'].max()) if not employee_summary.empty else 10,
                ),
                "주요 유형": st.column_config.TextColumn("주요 유형", width="medium"),
            },
            hide_index=True,
            use_container_width=True
        )
        
        st.caption("💡 왼쪽 사이드바에서 직원을 선택하면 '개별 리포트' 탭에서 상세 내용을 확인할 수 있습니다.")
    else:
        st.info("직원 평가 데이터가 없습니다.")

# ============================================
# 탭 3: 개별 리포트 (Deep Dive)
# ============================================
with tab3:
    if is_individual_view:
        # 개별 프로필 섹션
        st.subheader(f"👤 {selected_user} 상세 리포트")
        
        user_data = df_emp_eval[df_emp_eval['target_user_name'] == selected_user]
        
        if not user_data.empty:
            # 프로필 요약
            profile_col1, profile_col2, profile_col3 = st.columns(3)
            
            total_user_issues = len(user_data)
            top_user_type = user_data['evaluation_type'].value_counts().idxmax() if not user_data.empty else "N/A"
            top_user_category = user_data['category'].value_counts().idxmax() if not user_data.empty else "N/A"
            
            with profile_col1:
                st.metric("총 지적 횟수", f"{total_user_issues}건")
            with profile_col2:
                st.metric("주요 지적 유형", top_user_type)
            with profile_col3:
                st.metric("취약 카테고리", top_user_category)
            
            st.markdown("---")
            
            # 누락 유형별 분석
            st.subheader("누락 유형별 분석")
            
            # 평가 유형별 지적 횟수 (막대그래프)
            eval_types = ['누락', '내용부족', '오타', '문법', '오류']
            type_data = user_data['evaluation_type'].value_counts().reset_index()
            type_data.columns = ['type', 'count']
            
            # 모든 평가유형 포함
            full_type_data = pd.DataFrame({'type': eval_types})
            full_type_data = full_type_data.merge(type_data, on='type', how='left').fillna(0)
            full_type_data['count'] = full_type_data['count'].astype(int)
            
            # 평가유형별 색상 지정
            type_colors = alt.Scale(
                domain=['누락', '내용부족', '오타', '문법', '오류'],
                range=['#dc3545', '#fd7e14', '#ffc107', '#20c997', '#6f42c1']
            )
            
            # 바 차트로 표현
            type_bar = alt.Chart(full_type_data).mark_bar().encode(
                x=alt.X('type:N', title='평가 유형', sort=eval_types),
                y=alt.Y('count:Q', title='건수'),
                color=alt.Color('type:N', title='유형', scale=type_colors, legend=None),
                tooltip=[
                    alt.Tooltip('type:N', title='유형'),
                    alt.Tooltip('count:Q', title='건수')
                ]
            ).properties(height=250)
            
            # 건수 텍스트 표시
            text = alt.Chart(full_type_data).mark_text(
                align='center',
                baseline='bottom',
                dy=-5
            ).encode(
                x=alt.X('type:N', sort=eval_types),
                y=alt.Y('count:Q'),
                text=alt.Text('count:Q', format='d')
            )
            
            st.altair_chart(type_bar + text, use_container_width=True)
            
            st.markdown("---")
            
            # 평가 이력 테이블
            st.subheader("📋 평가 이력")
            
            # 날짜순 정렬
            user_data_sorted = user_data.sort_values('evaluation_date', ascending=False)
            
            # 데이터프레임 생성
            eval_history_df = pd.DataFrame({
                '평가일자': user_data_sorted['evaluation_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else str(x)
                ),
                '해당날짜': user_data_sorted['target_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and isinstance(x, (pd.Timestamp, date)) else ''
                ),
                '카테고리': user_data_sorted['category'],
                '평가유형': user_data_sorted['evaluation_type'],
                '코멘트': user_data_sorted['comment'].apply(
                    lambda x: (x[:50] + '...') if isinstance(x, str) and len(x) > 50 else (x if pd.notna(x) else '')
                )
            })
            
            st.dataframe(
                eval_history_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "평가일자": st.column_config.TextColumn("평가일자", width="small"),
                    "해당날짜": st.column_config.TextColumn("해당날짜", width="small"),
                    "카테고리": st.column_config.TextColumn("카테고리", width="small"),
                    "평가유형": st.column_config.TextColumn("평가유형", width="small"),
                    "코멘트": st.column_config.TextColumn("코멘트", width="large")
                }
            )
        else:
            st.info(f"{selected_user}님의 평가 기록이 없습니다.")
    else:
        st.info("👈 왼쪽 사이드바에서 직원을 선택하면 상세 리포트를 확인할 수 있습니다.")
        
        # 전체 요약 표시
        st.subheader("전체 직원 요약")
        if not df_emp_eval.empty:
            summary_stats = df_emp_eval.groupby('target_user_name').size().describe()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("평균 지적 건수", f"{summary_stats['mean']:.1f}건")
            with col2:
                st.metric("최대 지적 건수", f"{int(summary_stats['max'])}건")
            with col3:
                st.metric("총 평가 직원 수", f"{int(summary_stats['count'])}명")

# --- 푸터 ---
st.markdown("---")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
