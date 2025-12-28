"""Daily info repository for database operations."""

from typing import List, Dict, Optional
from modules.db_connection import db_transaction
from .base import BaseRepository


class DailyInfoRepository(BaseRepository):
    """Repository for daily info and related child tables operations."""
    
    def find_existing_record_id(self, customer_id: int, record_date) -> Optional[int]:
        """Find existing record ID for a customer and date."""
        query = """
            SELECT record_id FROM daily_infos 
            WHERE customer_id=%s AND date=%s
        """
        result = self._execute_query_one(query, (customer_id, record_date))
        return result['record_id'] if result else None
    
    def delete_daily_record(self, record_id: int) -> None:
        """Delete a daily record and all related child records."""
        if not record_id:
            return
        
        # 의존성 순서대로 삭제
        queries = [
            "DELETE FROM daily_physicals WHERE record_id=%s",
            "DELETE FROM daily_cognitives WHERE record_id=%s", 
            "DELETE FROM daily_nursings WHERE record_id=%s",
            "DELETE FROM daily_recoveries WHERE record_id=%s",
            "DELETE FROM daily_infos WHERE record_id=%s"
        ]
        
        with db_transaction() as cursor:
            for query in queries:
                cursor.execute(query, (record_id,))
    
    def insert_daily_info(self, customer_id: int, record: Dict) -> int:
        """Insert daily info record and return the record ID."""
        query = """
            INSERT INTO daily_infos (
                customer_id, date, start_time, end_time,
                total_service_time, transport_service, transport_vehicles
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_transaction_lastrowid(
            query, (
                customer_id, record["date"], 
                record.get("start_time"), record.get("end_time"),
                record.get("total_service_time"), 
                record.get("transport_service"),
                record.get("transport_vehicles")
            )
        )
    
    def replace_daily_physicals(self, record_id: int, record: Dict) -> None:
        """Replace daily physicals record for a record_id."""
        with db_transaction() as cursor:
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM daily_physicals WHERE record_id=%s", (record_id,))
            
            # 새 데이터 삽입
            cursor.execute("""
                INSERT INTO daily_physicals (
                    record_id, hygiene_care, bath_time, bath_method,
                    meal_breakfast, meal_lunch, meal_dinner,
                    toilet_care, mobility_care, note, writer_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
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
                record.get("writer_phy")
            ))
    
    def replace_daily_cognitives(self, record_id: int, record: Dict) -> None:
        """Replace daily cognitives record for a record_id."""
        with db_transaction() as cursor:
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM daily_cognitives WHERE record_id=%s", (record_id,))
            
            # 새 데이터 삽입
            cursor.execute("""
                INSERT INTO daily_cognitives (
                    record_id, cog_support, comm_support, note, writer_name
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                record_id,
                record.get("cog_support"),
                record.get("comm_support"),
                record.get("cognitive_note"),
                record.get("writer_cog")
            ))
    
    def replace_daily_nursings(self, record_id: int, record: Dict) -> None:
        """Replace daily nursings record for a record_id."""
        with db_transaction() as cursor:
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM daily_nursings WHERE record_id=%s", (record_id,))
            
            # 새 데이터 삽입
            cursor.execute("""
                INSERT INTO daily_nursings (
                    record_id, bp_temp, health_manage, nursing_manage,
                    emergency, note, writer_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                record_id,
                record.get("bp_temp"),
                record.get("health_manage"),
                record.get("nursing_manage"),
                record.get("emergency"),
                record.get("nursing_note"),
                record.get("writer_nur")
            ))
    
    def replace_daily_recoveries(self, record_id: int, record: Dict) -> None:
        """Replace daily recoveries record for a record_id."""
        with db_transaction() as cursor:
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM daily_recoveries WHERE record_id=%s", (record_id,))
            
            # 새 데이터 삽입
            cursor.execute("""
                INSERT INTO daily_recoveries (
                    record_id, prog_basic, prog_activity, prog_cognitive,
                    prog_therapy, prog_enhance_detail, note, writer_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record_id,
                record.get("prog_basic"),
                record.get("prog_activity"),
                record.get("prog_cognitive"),
                record.get("prog_therapy"),
                record.get("prog_enhance_detail"),
                record.get("functional_note"),
                record.get("writer_func")
            ))
    
    def save_parsed_data(self, records: List[Dict]) -> int:
        """Save parsed daily data in a single transaction."""
        saved_count = 0
        
        with db_transaction() as cursor:
            for record in records:
                # 고객 확인 또는 생성
                customer_id = self._get_or_create_customer_in_transaction(
                    cursor, record
                )
                record["customer_id"] = customer_id
                
                # 기존 레코드 확인
                cursor.execute(
                    "SELECT record_id FROM daily_infos WHERE customer_id=%s AND date=%s",
                    (customer_id, record["date"])
                )
                existing = cursor.fetchone()
                
                if existing:
                    self._delete_daily_record_in_transaction(cursor, existing[0])
                
                # 새 레코드 삽입
                cursor.execute("""
                    INSERT INTO daily_infos (
                        customer_id, date, start_time, end_time,
                        total_service_time, transport_service, transport_vehicles
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    customer_id, record["date"],
                    record.get("start_time"), record.get("end_time"),
                    record.get("total_service_time"),
                    record.get("transport_service"),
                    record.get("transport_vehicles")
                ))
                record_id = cursor.lastrowid
                
                # 하위 레코드들 삽입
                self._insert_physicals_in_transaction(cursor, record_id, record)
                self._insert_cognitives_in_transaction(cursor, record_id, record)
                self._insert_nursings_in_transaction(cursor, record_id, record)
                self._insert_recoveries_in_transaction(cursor, record_id, record)
                
                saved_count += 1
        
        return saved_count
    
    def get_customer_records(self, customer_id: int, start_date=None, end_date=None) -> List[Dict]:
        """Get all daily records for a customer within date range."""
        query = """
            SELECT 
                di.record_id, di.date, di.total_service_time,
                dp.note AS physical_note, dp.writer_name AS writer_physical,
                dp.meal_breakfast, dp.meal_lunch, dp.meal_dinner,
                dp.toilet_care, dp.bath_time,
                dn.bp_temp,
                dr.prog_therapy,
                dc.note AS cognitive_note, dc.writer_name AS writer_cognitive,
                dn.note AS nursing_note, dn.writer_name AS writer_nursing,
                dr.note AS functional_note, dr.writer_name AS writer_recovery
            FROM daily_infos di
            LEFT JOIN daily_physicals dp ON dp.record_id = di.record_id
            LEFT JOIN daily_cognitives dc ON dc.record_id = di.record_id
            LEFT JOIN daily_nursings dn ON dn.record_id = di.record_id
            LEFT JOIN daily_recoveries dr ON dr.record_id = di.record_id
            WHERE di.customer_id = %s
        """
        params = [customer_id]
        
        if start_date and end_date:
            query += " AND di.date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += " ORDER BY di.date DESC"
        
        return self._execute_query(query, tuple(params))
    
    def get_record_by_customer_and_date(self, customer_id: int, date) -> Optional[Dict]:
        """Get a specific daily record for a customer and date."""
        query = """
            SELECT record_id
            FROM daily_infos
            WHERE customer_id = %s AND date = %s
            LIMIT 1
        """
        result = self._execute_query_one(query, (customer_id, date))
        return result['record_id'] if result else None
    
    # 트랜잭션 처리를 위한 비공개 헬퍼 메서드들
    def _get_or_create_customer_in_transaction(self, cursor, record: Dict) -> int:
        """Get or create customer within an existing transaction."""
        name = record.get("customer_name")
        cursor.execute("SELECT customer_id FROM customers WHERE name = %s", (name,))
        result = cursor.fetchone()
        
        if result:
            customer_id = result[0]
            cursor.execute("""
                UPDATE customers SET
                    birth_date=%s, grade=%s, recognition_no=%s
                WHERE customer_id=%s
            """, (
                record.get("customer_birth_date"),
                record.get("customer_grade"),
                record.get("customer_recognition_no"),
                customer_id
            ))
            return customer_id
        else:
            cursor.execute("""
                INSERT INTO customers (
                    name, birth_date, grade, recognition_no
                ) VALUES (%s, %s, %s, %s)
            """, (
                name,
                record.get("customer_birth_date"),
                record.get("customer_grade"),
                record.get("customer_recognition_no")
            ))
            return cursor.lastrowid
    
    def _delete_daily_record_in_transaction(self, cursor, record_id: int) -> None:
        """Delete daily record within an existing transaction."""
        cursor.execute("DELETE FROM daily_physicals WHERE record_id=%s", (record_id,))
        cursor.execute("DELETE FROM daily_cognitives WHERE record_id=%s", (record_id,))
        cursor.execute("DELETE FROM daily_nursings WHERE record_id=%s", (record_id,))
        cursor.execute("DELETE FROM daily_recoveries WHERE record_id=%s", (record_id,))
        cursor.execute("DELETE FROM daily_infos WHERE record_id=%s", (record_id,))
    
    def _insert_physicals_in_transaction(self, cursor, record_id: int, record: Dict) -> None:
        """Insert physicals record within an existing transaction."""
        cursor.execute("""
            INSERT INTO daily_physicals (
                record_id, hygiene_care, bath_time, bath_method,
                meal_breakfast, meal_lunch, meal_dinner,
                toilet_care, mobility_care, note, writer_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
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
            record.get("writer_phy")
        ))
    
    def _insert_cognitives_in_transaction(self, cursor, record_id: int, record: Dict) -> None:
        """Insert cognitives record within an existing transaction."""
        cursor.execute("""
            INSERT INTO daily_cognitives (
                record_id, cog_support, comm_support, note, writer_name
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            record_id,
            record.get("cog_support"),
            record.get("comm_support"),
            record.get("cognitive_note"),
            record.get("writer_cog")
        ))
    
    def _insert_nursings_in_transaction(self, cursor, record_id: int, record: Dict) -> None:
        """Insert nursings record within an existing transaction."""
        cursor.execute("""
            INSERT INTO daily_nursings (
                record_id, bp_temp, health_manage, nursing_manage,
                emergency, note, writer_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            record_id,
            record.get("bp_temp"),
            record.get("health_manage"),
            record.get("nursing_manage"),
            record.get("emergency"),
            record.get("nursing_note"),
            record.get("writer_nur")
        ))
    
    def _insert_recoveries_in_transaction(self, cursor, record_id: int, record: Dict) -> None:
        """Insert recoveries record within an existing transaction."""
        cursor.execute("""
            INSERT INTO daily_recoveries (
                record_id, prog_basic, prog_activity, prog_cognitive,
                prog_therapy, prog_enhance_detail, note, writer_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            record_id,
            record.get("prog_basic"),
            record.get("prog_activity"),
            record.get("prog_cognitive"),
            record.get("prog_therapy"),
            record.get("prog_enhance_detail"),
            record.get("functional_note"),
            record.get("writer_func")
        ))
