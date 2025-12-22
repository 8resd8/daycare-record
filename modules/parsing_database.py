import mysql.connector
import streamlit as st

def get_db_connection():
    return mysql.connector.connect(**st.secrets["mysql"])

def get_or_create_customer(cursor, name):
    cursor.execute("SELECT customer_id FROM customers WHERE name = %s", (name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO customers (name) VALUES (%s)", (name,))
        return cursor.lastrowid

def save_parsed_data(records):
    """ 파싱된 데이터를 DB에 저장하는 메인 함수 """
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0
    try:
        for rec in records:
            cust_id = get_or_create_customer(cursor, rec['customer_name'])

            # [Master]
            cursor.execute("SELECT record_id FROM daily_records WHERE customer_id=%s AND date=%s", (cust_id, rec['date']))
            existing = cursor.fetchone()
            if existing:
                record_id = existing[0]
                cursor.execute("UPDATE daily_records SET start_time=%s, end_time=%s WHERE record_id=%s", (rec['start_time'], rec['end_time'], record_id))
            else:
                cursor.execute("INSERT INTO daily_records (customer_id, date, start_time, end_time) VALUES (%s,%s,%s,%s)", (cust_id, rec['date'], rec['start_time'], rec['end_time']))
                record_id = cursor.lastrowid

            # [Detail 1] Physical
            cursor.execute("DELETE FROM physical_records WHERE record_id=%s", (record_id,))
            cursor.execute("""
                           INSERT INTO physical_records (record_id, hygiene_care, bath_time, bath_method, meal_breakfast, meal_lunch, meal_dinner, toilet_care, mobility_care, note, writer_name)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           """, (record_id, rec['hygiene_care'], rec['bath_time'], rec['bath_method'], rec['meal_breakfast'], rec['meal_lunch'], rec['meal_dinner'], rec['toilet_care'], rec['mobility_care'], rec['physical_note'], rec['writer_phy']))

            # [Detail 2] Cognitive
            cursor.execute("DELETE FROM cognitive_records WHERE record_id=%s", (record_id,))
            cursor.execute("INSERT INTO cognitive_records (record_id, cog_support, comm_support, note, writer_name) VALUES (%s,%s,%s,%s,%s)", (record_id, rec['cog_support'], rec['comm_support'], rec['cognitive_note'], rec['writer_cog']))

            # [Detail 3] Nursing
            cursor.execute("DELETE FROM nursing_records WHERE record_id=%s", (record_id,))
            cursor.execute("INSERT INTO nursing_records (record_id, bp_temp, health_manage, nursing_manage, emergency, note, writer_name) VALUES (%s,%s,%s,%s,%s,%s,%s)", (record_id, rec['bp_temp'], rec['health_manage'], rec['nursing_manage'], rec['emergency'], rec['nursing_note'], rec['writer_nur']))

            # [Detail 4] Recovery
            cursor.execute("DELETE FROM recovery_records WHERE record_id=%s", (record_id,))
            cursor.execute("INSERT INTO recovery_records (record_id, prog_basic, prog_activity, prog_cognitive, prog_therapy, note, writer_name) VALUES (%s,%s,%s,%s,%s,%s,%s)", (record_id, rec['prog_basic'], rec['prog_activity'], rec['prog_cognitive'], rec['prog_therapy'], rec['functional_note'], rec['writer_func']))

            saved_count += 1
        conn.commit()
        return saved_count
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()