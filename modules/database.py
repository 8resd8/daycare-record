"""Database module - now using repository pattern.

This module provides high-level database operations using repositories.
Direct SQL queries have been moved to repository classes.
"""

from modules.repositories import WeeklyStatusRepository, DailyInfoRepository


# 리포지토리 초기화
weekly_status_repo = WeeklyStatusRepository()
daily_info_repo = DailyInfoRepository()


def save_weekly_status(*, customer_id: int, start_date, end_date, report_text: str) -> None:
    """Save or update weekly status report."""
    weekly_status_repo.save_weekly_status(customer_id, start_date, end_date, report_text)


def load_weekly_status(*, customer_id: int, start_date, end_date) -> str | None:
    """Load weekly status report for a specific period."""
    return weekly_status_repo.load_weekly_status(customer_id, start_date, end_date)


def save_parsed_data(records):
    """Save parsed data to database."""
    return daily_info_repo.save_parsed_data(records)


def get_db_connection():
    """Get a database connection using Streamlit secrets."""
    import streamlit as st
    import mysql.connector
    return mysql.connector.connect(**st.secrets["mysql"])
