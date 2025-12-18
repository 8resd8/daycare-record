import pdfplumber
import re

class CareRecordParser:
    def __init__(self, pdf_file):
        self.pdf_file = pdf_file
        self.parsed_data = []
        self.appendix_notes = {}

    def parse(self):
        with pdfplumber.open(self.pdf_file) as pdf:
            for page in pdf.pages:
                self._parse_page(page)

        self._merge_appendix_to_main()
        return self.parsed_data

    def _parse_page(self, page):
        # 테이블 추출
        table = page.extract_table(table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 4,
        })

        if not table: return

        # [디버그 수정] 별지 테이블 감지 로직 강화
        # 헤더를 확인하는 대신, 데이터 패턴(날짜+긴글)을 확인하여 별지로 등록
        if self._is_appendix_table(table):
            self._parse_appendix_table(table)
            return

        # 메인 기록지 파싱
        idx = self._find_row_indices(table)
        if idx["date"] == -1: return

        date_row = table[idx["date"]]

        for col_idx in range(len(date_row)):
            raw_date = date_row[col_idx]
            if not raw_date or "월/일" in str(raw_date): continue

            current_date = self._clean_date(raw_date)
            if not current_date: continue

            record = {
                "date": current_date,
                "customer_name": self._extract_customer_name(table),
                "start_time": None, "end_time": None,

                # 1. 신체활동지원
                "hygiene_care": "미실시",
                "bath_time": "-", "bath_method": "-",
                "meal_breakfast": "-", "meal_lunch": "-", "meal_dinner": "-",
                "toilet_care": "-",
                "mobility_care": "미실시",
                "physical_note": "",
                "writer_phy": None,

                # 2. 인지관리
                "cog_support": "미실시", "comm_support": "미실시",
                "cognitive_note": "",
                "writer_cog": None,

                # 3. 간호관리
                "bp_temp": "-", "health_manage": "미실시",
                "nursing_manage": "미실시", "emergency": "미실시",
                "nursing_note": "",
                "writer_nur": None,

                # 4. 기능회복
                "prog_basic": "미실시", "prog_activity": "미실시",
                "prog_cognitive": "미실시", "prog_therapy": "미실시",
                "functional_note": "",
                "writer_func": None
            }

            # --- 데이터 매핑 ---
            if idx["time"] != -1:
                val = self._get_cell(table, idx["time"], col_idx)
                if val and "~" in val:
                    times = val.split("~")
                    record["start_time"] = times[0].strip()
                    record["end_time"] = times[1].strip()

            if idx["hygiene"] != -1: record["hygiene_care"] = self._check_status(self._get_cell(table, idx["hygiene"], col_idx))

            # [요청 2] 목욕 값이 없거나 '-'일 때 처리
            b_time = self._get_cell(table, idx["bath_time"], col_idx) if idx["bath_time"] != -1 else ""
            b_method = self._get_cell(table, idx["bath_method"], col_idx) if idx["bath_method"] != -1 else ""

            # 값이 없거나 '-'만 있으면 '없음'으로 통일
            if (not b_time or b_time == "-") and (not b_method or b_method == "-"):
                record["bath_time"] = "없음"
                record["bath_method"] = "" # 병합 시 깔끔하게 보이도록
            else:
                record["bath_time"] = b_time
                record["bath_method"] = b_method

            # 식사
            if idx["meal_bk"] != -1: record["meal_breakfast"] = self._get_cell(table, idx["meal_bk"], col_idx)
            if idx["meal_ln"] != -1: record["meal_lunch"] = self._get_cell(table, idx["meal_ln"], col_idx)
            if idx["meal_dn"] != -1: record["meal_dinner"] = self._get_cell(table, idx["meal_dn"], col_idx)

            if idx["excretion"] != -1: record["toilet_care"] = self._get_cell(table, idx["excretion"], col_idx)
            if idx["mobility"] != -1: record["mobility_care"] = self._check_status(self._get_cell(table, idx["mobility"], col_idx))

            # 인지/간호/기능 상태값
            if idx["cog_sup"] != -1: record["cog_support"] = self._check_status(self._get_cell(table, idx["cog_sup"], col_idx))
            if idx["comm_sup"] != -1: record["comm_support"] = self._check_status(self._get_cell(table, idx["comm_sup"], col_idx))
            if idx["bp_temp"] != -1: record["bp_temp"] = self._get_cell(table, idx["bp_temp"], col_idx)
            if idx["health"] != -1: record["health_manage"] = self._check_status(self._get_cell(table, idx["health"], col_idx))
            if idx["nursing"] != -1: record["nursing_manage"] = self._check_status(self._get_cell(table, idx["nursing"], col_idx))
            if idx["emergency"] != -1: record["emergency"] = self._check_status(self._get_cell(table, idx["emergency"], col_idx))

            if idx["prog_basic"] != -1: record["prog_basic"] = self._check_status(self._get_cell(table, idx["prog_basic"], col_idx))
            if idx["prog_act"] != -1: record["prog_activity"] = self._check_status(self._get_cell(table, idx["prog_act"], col_idx))
            if idx["prog_cog"] != -1: record["prog_cognitive"] = self._check_status(self._get_cell(table, idx["prog_cog"], col_idx))
            if idx["prog_ther"] != -1: record["prog_therapy"] = self._check_status(self._get_cell(table, idx["prog_ther"], col_idx))

            # 특이사항
            if idx["note_phy"] != -1: record["physical_note"] = self._get_cell(table, idx["note_phy"], col_idx)
            if idx["note_cog"] != -1: record["cognitive_note"] = self._get_cell(table, idx["note_cog"], col_idx)
            if idx["note_nur"] != -1: record["nursing_note"] = self._get_cell(table, idx["note_nur"], col_idx)
            if idx["note_func"] != -1: record["functional_note"] = self._get_cell(table, idx["note_func"], col_idx)

            # 작성자
            if idx["writer_phy"] != -1: record["writer_phy"] = self._get_cell(table, idx["writer_phy"], col_idx)
            if idx["writer_cog"] != -1: record["writer_cog"] = self._get_cell(table, idx["writer_cog"], col_idx)
            if idx["writer_nur"] != -1: record["writer_nur"] = self._get_cell(table, idx["writer_nur"], col_idx)
            if idx["writer_func"] != -1: record["writer_func"] = self._get_cell(table, idx["writer_func"], col_idx)

            self.parsed_data.append(record)

    def _is_appendix_table(self, table):
        """ 테이블 행 중에 날짜(YYYY.MM.DD) 형식의 데이터가 포함되어 있으면 별지로 간주 """
        for row in table:
            if len(row) < 2: continue
            first_col = str(row[0]).strip()
            # 2025.11.14 형식 체크
            if re.match(r'\d{4}[\.-]\d{2}[\.-]\d{2}', first_col):
                return True
        return False

    def _parse_appendix_table(self, table):
        for row in table:
            try:
                # 헤더(날짜/내용) 행은 건너뜀 (날짜 형식이 아닐 테니 정규식에서 걸러짐)
                raw_date, content = row[0], row[1]
                if not raw_date or not content: continue

                # 날짜 정규식 체크 (YYYY.MM.DD 또는 YYYY-MM-DD)
                if not re.match(r'\d{4}[\.-]\d{2}[\.-]\d{2}', str(raw_date)):
                    continue

                clean_date = str(raw_date).replace(".", "-").strip()
                clean_content = str(content).replace("\n", " ").strip()

                if clean_date in self.appendix_notes:
                    self.appendix_notes[clean_date] += " / " + clean_content
                else:
                    self.appendix_notes[clean_date] = clean_content
            except: continue

    def _merge_appendix_to_main(self):
        target_fields = ['physical_note', 'cognitive_note', 'nursing_note', 'functional_note']
        for record in self.parsed_data:
            r_date = record['date']
            if r_date in self.appendix_notes:
                appendix = self.appendix_notes[r_date]
                for field in target_fields:
                    # [요청 4] [별지] 태그 삭제하고 내용만 넣음
                    if self._is_placeholder(record[field]):
                        record[field] = f"{appendix}"
            else:
                for field in target_fields:
                    if self._is_placeholder(record[field]):
                        record[field] += " (⚠️내용 미발견)"

    def _find_row_indices(self, table):
        idx = {
            "date": -1, "time": -1,
            "hygiene": -1, "bath_time": -1, "bath_method": -1,
            "meal_bk": -1, "meal_ln": -1, "meal_dn": -1,
            "excretion": -1, "mobility": -1,
            "note_phy": -1, "writer_phy": -1,
            "cog_sup": -1, "comm_sup": -1, "note_cog": -1, "writer_cog": -1,
            "bp_temp": -1, "health": -1, "nursing": -1, "emergency": -1, "note_nur": -1, "writer_nur": -1,
            "prog_basic": -1, "prog_act": -1, "prog_cog": -1, "prog_ther": -1, "note_func": -1, "writer_func": -1
        }
        note_rows, writer_rows = [], []
        for i, row in enumerate(table):
            label = "".join([str(c).replace("\n", "").replace(" ", "") for c in row[:3] if c])

            if "년월/일" in label: idx["date"] = i
            elif "시작시간" in label: idx["time"] = i

            # 신체
            elif "세면" in label: idx["hygiene"] = i
            elif "소요시간" in label: idx["bath_time"] = i
            elif "목욕" in label and "방법" in label: idx["bath_method"] = i
            elif "아침" in label: idx["meal_bk"] = i
            elif "점심" in label: idx["meal_ln"] = i
            elif "저녁" in label: idx["meal_dn"] = i
            elif "화장실" in label or "기저귀" in label: idx["excretion"] = i
            elif "이동도움" in label: idx["mobility"] = i

            # 인지
            elif "인지관리지원" in label: idx["cog_sup"] = i
            elif "의사소통" in label: idx["comm_sup"] = i

            # 간호
            elif "혈압" in label: idx["bp_temp"] = i
            elif "건강관리" in label: idx["health"] = i
            elif "간호관리" in label: idx["nursing"] = i
            elif "응급" in label: idx["emergency"] = i

            # 기능
            elif "기본동작" in label: idx["prog_basic"] = i
            elif "인지활동" in label: idx["prog_act"] = i
            elif "인지기능" in label and "향상" in label: idx["prog_cog"] = i
            elif "물리" in label: idx["prog_ther"] = i

            elif "특이사항" in label: note_rows.append(i)
            elif "작성자" in label: writer_rows.append(i)

        if len(note_rows) >= 1: idx["note_phy"] = note_rows[0]
        if len(note_rows) >= 2: idx["note_cog"] = note_rows[1]
        if len(note_rows) >= 3: idx["note_nur"] = note_rows[2]
        if len(note_rows) >= 4: idx["note_func"] = note_rows[3]

        if len(writer_rows) >= 1: idx["writer_phy"] = writer_rows[0]
        if len(writer_rows) >= 2: idx["writer_cog"] = writer_rows[1]
        if len(writer_rows) >= 3: idx["writer_nur"] = writer_rows[2]
        if len(writer_rows) >= 4: idx["writer_func"] = writer_rows[3]
        return idx

    def _get_cell(self, table, row, col):
        try: return str(table[row][col]).replace("\n", " ").strip() if table[row][col] else ""
        except: return ""

    def _clean_date(self, date_str):
        try:
            clean = re.sub(r'\(.*\)', '', str(date_str)).replace('.', '-').strip()
            if '/' in clean:
                md = clean.split('/')
                return f"2025-{int(md[0]):02d}-{int(md[1]):02d}"
            return clean
        except: return None

    def _extract_customer_name(self, table):
        try:
            for cell in table[0]:
                if cell and len(str(cell)) > 1 and "수급자" not in str(cell): return str(cell).replace(" ", "")
            return "미상"
        except: return "미상"

    def _is_placeholder(self, text):
        clean = str(text).replace(" ", "")
        return any(k in clean for k in ["별지", "첨부", "참조"]) and "특이사항없음" not in clean

    def _check_status(self, text):
        # [요청 3] 상태 텍스트 변경
        if not text: return "미실시"
        clean = text.strip()
        if any(c in clean for c in ["■", "Π", "V", "O", "☑"]):
            return "완료"
        return "미실시"