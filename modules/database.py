import mysql.connector
import streamlit as st

def save_weekly_status(*, customer_id: int, start_date, end_date, report_text: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO weekly_status (customer_id, start_date, end_date, report_text)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                report_text=VALUES(report_text),
                updated_at=CURRENT_TIMESTAMP
            """,
            (customer_id, start_date, end_date, report_text),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def load_weekly_status(*, customer_id: int, start_date, end_date) -> str | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT report_text
            FROM weekly_status
            WHERE customer_id=%s AND start_date=%s AND end_date=%s
            """,
            (customer_id, start_date, end_date),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()
        conn.close()


def resolve_customer_id(*, name: str, recognition_no: str | None = None, birth_date=None) -> int | None:
    """Resolve customer_id for weekly_status storage.

    Priority:
    1) recognition_no (unique-ish)
    2) name + birth_date
    3) name (fallback, newest)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if recognition_no:
            cursor.execute(
                "SELECT customer_id FROM customers WHERE recognition_no=%s ORDER BY customer_id DESC LIMIT 1",
                (recognition_no,),
            )
            row = cursor.fetchone()
            if row:
                return int(row[0])

        if name and birth_date:
            cursor.execute(
                "SELECT customer_id FROM customers WHERE name=%s AND birth_date=%s ORDER BY customer_id DESC LIMIT 1",
                (name, birth_date),
            )
            row = cursor.fetchone()
            if row:
                return int(row[0])

        if name:
            cursor.execute(
                "SELECT customer_id FROM customers WHERE name=%s ORDER BY customer_id DESC LIMIT 1",
                (name,),
            )
            row = cursor.fetchone()
            if row:
                return int(row[0])
        return None
    finally:
        cursor.close()
        conn.close()


def get_db_connection():
    return mysql.connector.connect(**st.secrets["mysql"])


def get_or_create_customer(cursor, record):
    name = record.get("customer_name")
    cursor.execute("SELECT customer_id FROM customers WHERE name = %s", (name,))
    result = cursor.fetchone()
    payload = (
        record.get("customer_birth_date"),
        record.get("customer_grade"),
        record.get("customer_recognition_no"),
        record.get("facility_name"),
        record.get("facility_code"),
    )
    if result:
        customer_id = result[0]
        cursor.execute(
            """
            UPDATE customers SET
                birth_date=%s,
                grade=%s,
                recognition_no=%s,
                facility_name=%s,
                facility_code=%s
            WHERE customer_id=%s
            """,
            (*payload, customer_id),
        )
        return customer_id

    cursor.execute(
        """
        INSERT INTO customers (
            name, birth_date, grade, recognition_no, facility_name, facility_code
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (name, *payload),
    )
    return cursor.lastrowid


def _find_existing_record_id(cursor, customer_id, record_date):
    cursor.execute(
        "SELECT record_id FROM daily_infos WHERE customer_id=%s AND date=%s",
        (customer_id, record_date),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _delete_daily_record(cursor, record_id):
    if not record_id:
        return
    cursor.execute("DELETE FROM daily_physicals WHERE record_id=%s", (record_id,))
    cursor.execute("DELETE FROM daily_cognitives WHERE record_id=%s", (record_id,))
    cursor.execute("DELETE FROM daily_nursings WHERE record_id=%s", (record_id,))
    cursor.execute("DELETE FROM daily_recoveries WHERE record_id=%s", (record_id,))
    cursor.execute("DELETE FROM daily_infos WHERE record_id=%s", (record_id,))


def _insert_daily_info(cursor, customer_id, record):
    payload = (
        record.get("start_time"),
        record.get("end_time"),
        record.get("total_service_time"),
        record.get("transport_service"),
        record.get("transport_vehicles"),
    )
    cursor.execute(
        """
        INSERT INTO daily_infos (
            customer_id, date, start_time, end_time,
            total_service_time, transport_service, transport_vehicles
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (customer_id, record["date"], *payload),
    )
    return cursor.lastrowid


def _replace_daily_physicals(cursor, record_id, record):
    cursor.execute("DELETE FROM daily_physicals WHERE record_id=%s", (record_id,))
    cursor.execute(
        """
        INSERT INTO daily_physicals (
            record_id, hygiene_care, bath_time, bath_method,
            meal_breakfast, meal_lunch, meal_dinner,
            toilet_care, mobility_care, note, writer_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            record_id,
            record.get("hygiene_care"),
            record.get("bath_time"),
            record.get("bath_method"),
            record.get("meal_breakfast"),
            record.get("meal_lunch"),
            record.get("meal_dinner"),
            record.get("toilet_care"),
            record.get("mobility_care"),
            record.get("physical_note"),
            record.get("writer_phy"),
        ),
    )


def _replace_daily_cognitives(cursor, record_id, record):
    cursor.execute("DELETE FROM daily_cognitives WHERE record_id=%s", (record_id,))
    cursor.execute(
        """
        INSERT INTO daily_cognitives (
            record_id, cog_support, comm_support, note, writer_name
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (
            record_id,
            record.get("cog_support"),
            record.get("comm_support"),
            record.get("cognitive_note"),
            record.get("writer_cog"),
        ),
    )


def _replace_daily_nursings(cursor, record_id, record):
    cursor.execute("DELETE FROM daily_nursings WHERE record_id=%s", (record_id,))
    cursor.execute(
        """
        INSERT INTO daily_nursings (
            record_id, bp_temp, health_manage, nursing_manage,
            emergency, note, writer_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            record_id,
            record.get("bp_temp"),
            record.get("health_manage"),
            record.get("nursing_manage"),
            record.get("emergency"),
            record.get("nursing_note"),
            record.get("writer_nur"),
        ),
    )


def _replace_daily_recoveries(cursor, record_id, record):
    cursor.execute("DELETE FROM daily_recoveries WHERE record_id=%s", (record_id,))
    cursor.execute(
        """
        INSERT INTO daily_recoveries (
            record_id, prog_basic, prog_activity, prog_cognitive,
            prog_therapy, prog_enhance_detail, note, writer_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            record_id,
            record.get("prog_basic"),
            record.get("prog_activity"),
            record.get("prog_cognitive"),
            record.get("prog_therapy"),
            record.get("prog_enhance_detail"),
            record.get("functional_note"),
            record.get("writer_func"),
        ),
    )


def save_parsed_data(records):
    """파싱된 데이터를 새 스키마에 저장"""
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0
    try:
        for record in records:
            customer_id = get_or_create_customer(cursor, record)
            record["customer_id"] = customer_id
            existing_id = _find_existing_record_id(cursor, customer_id, record["date"])
            if existing_id:
                _delete_daily_record(cursor, existing_id)

            record_id = _insert_daily_info(cursor, customer_id, record)

            _replace_daily_physicals(cursor, record_id, record)
            _replace_daily_cognitives(cursor, record_id, record)
            _replace_daily_nursings(cursor, record_id, record)
            _replace_daily_recoveries(cursor, record_id, record)

            saved_count += 1

        conn.commit()
        return saved_count
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
