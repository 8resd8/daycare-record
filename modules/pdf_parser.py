import pdfplumber
import re
import os

class CareRecordParser:
    STATUS_DONE = "완료"
    STATUS_NOT_DONE = "미실시"
    TRANSPORT_PROVIDED = "제공"
    TRANSPORT_NOT_PROVIDED = "미제공"
    ABSENCE_TOTAL_STATUSES = {"미이용", "결석"}
    CHECKED_SYMBOLS = ("■", "Π", "V", "O", "☑")
    BATH_NOT_AVAILABLE = "없음"

    def __init__(self, pdf_file):
        self.pdf_file = pdf_file
        self.parsed_data = []
        self.appendix_notes = {}
        self._debug = os.getenv("PARSER_DEBUG") == "1"
        self._basic_info = {}
        self._personal_info = {}

    def _normalize_text(self, text):
        s = str(text).replace("\n", "").replace(" ", "")
        return s.replace("ㆍ", "").replace("·", "")

    def _normalize_row_text(self, row):
        return "".join([self._normalize_text(c) for c in row if c])

    def _pick_nearby_text(self, table, row, col, *, window=3, min_len=2):
        try:
            row_data = table[row]
        except Exception:
            return ""

        def _is_labelish(v: str) -> bool:
            vv = self._normalize_text(v)
            return any(k in vv for k in [
                "신체인지기능향상프로그램",
                "향상프로그램",
                "프로그램",
                "향상",
                "항목",
                "내용",
            ])

        best = ""
        # 1) 같은 행 전체에서 가장 긴 텍스트를 우선 채택 (라벨성 텍스트 제외)
        for j in range(len(row_data)):
            v = self._get_cell(table, row, j)
            if not v:
                continue
            if len(v.strip()) < min_len:
                continue
            if _is_labelish(v):
                continue
            if len(v) > len(best):
                best = v

        # 2) 그래도 못 찾으면 주변 window 내에서라도 텍스트를 찾음
        if not best:
            start = max(0, col - window)
            end = min(len(row_data) - 1, col + window)
            for j in range(start, end + 1):
                v = self._get_cell(table, row, j)
                if not v:
                    continue
                if len(v.strip()) < min_len:
                    continue
                if _is_labelish(v):
                    continue
                if len(v) > len(best):
                    best = v

        return best

    def parse(self):
        final_records = []

        with pdfplumber.open(self.pdf_file) as pdf:
            pages = pdf.pages
            page_groups = self._split_page_groups(pages)

            for group_pages in page_groups:
                if not group_pages:
                    continue

                # 그룹 단위로 상태 초기화
                self.parsed_data = []
                self.appendix_notes = {}

                self._personal_info = self._parse_personal_info(group_pages)
                self._basic_info = self._parse_basic_info_block(group_pages)

                for page in group_pages:
                    self._parse_page(page)

                self._merge_appendix_to_main()
                final_records.extend(self.parsed_data)

        self.parsed_data = final_records
        return self.parsed_data

    def _split_page_groups(self, pages):
        """한 PDF 안에 여러 수급자 기록지가 연속으로 존재하는 경우 그룹을 분리"""
        if not pages:
            return []

        groups = []
        current_group = []

        for page in pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            normalized = text.replace(" ", "")
            is_header = (
                "장기요양급여제공기록지" in normalized
                or "노인장기요양보험법시행규칙" in normalized
            )

            if is_header:
                if current_group:
                    groups.append(current_group)
                current_group = [page]
            else:
                if current_group:
                    current_group.append(page)
                elif text.strip():
                    current_group = [page]

        if current_group:
            groups.append(current_group)

        # 헤더를 찾지 못한 경우 전체 페이지를 하나의 그룹으로 반환
        return groups or [list(pages)]

    def _parse_page(self, page):
        # 1. 페이지 내의 섹션 헤더 위치 찾기 (별지 구분용)
        section_headers = []
        # [수정] "cog" (인지관리) 키워드 추가됨
        keywords = [
            ("phy", ["신체활동지원", "신체 활동 지원", "신체활동"]),
            ("nur", ["건강 및 간호", "간호관리", "건강관리"]),
            ("func", ["기능회복", "기능 회복"]),
            ("cog", ["인지관리", "의사소통", "인지 관리", "인지지원"])
        ]

        for key, labels in keywords:
            for label in labels:
                matches = page.search(label)
                if matches:
                    # 가장 마지막에 발견된 해당 키워드의 위치를 사용
                    for match in matches:
                        section_headers.append({"type": key, "top": match["top"]})

        # 위치 순서대로 정렬 (위 -> 아래)
        section_headers.sort(key=lambda x: x["top"])

        # 2. 페이지 내 모든 테이블 찾기
        tables = page.find_tables(table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 4,
        })

        if not tables:
            return

        basic_info = self._basic_info or {}

        for table_obj in tables:
            # 테이블 데이터 추출
            table_data = table_obj.extract()
            if not table_data: continue

            # [별지 테이블 판별 및 카테고리 할당]
            if self._is_appendix_table(table_data):
                table_top = table_obj.bbox[1]
                category = "func" # 기본값 (헤더를 못 찾을 경우 대비)

                # 테이블보다 위에 있는 헤더 중 가장 가까운 것 찾기
                closest_diff = float('inf')
                for header in section_headers:
                    if header["top"] < table_top:
                        diff = table_top - header["top"]
                        if diff < closest_diff:
                            closest_diff = diff
                            category = header["type"]

                # 디버깅용 출력
                if self._debug:
                    print(f"[PARSER_DEBUG] Appendix Table Found. Cat: {category}, Rows: {len(table_data)}")

                self._parse_appendix_table(table_data, category)
                continue

            # --- 메인 기록지 파싱 로직 ---
            idx = self._find_row_indices(table_data)
            if idx["date"] == -1: continue # 날짜 행이 없으면 스킵

            date_row = table_data[idx["date"]]

            for col_idx in range(len(date_row)):
                raw_date = date_row[col_idx]
                if not raw_date or "월/일" in str(raw_date): continue

                current_date = self._clean_date(raw_date)
                if not current_date: continue

                customer_name = self._personal_info.get("customer_name") or self._extract_customer_name(table_data)

                record = {
                    "date": current_date,
                    "customer_name": customer_name,
                    "customer_birth_date": self._personal_info.get("birth_date"),
                    "customer_grade": self._personal_info.get("care_grade"),
                    "customer_recognition_no": self._personal_info.get("recognition_no"),
                    "facility_name": self._personal_info.get("facility_name"),
                    "facility_code": self._personal_info.get("facility_code"),
                    "start_time": basic_info.get("start_time"),
                    "end_time": basic_info.get("end_time"),
                    "total_service_time": basic_info.get("total_service_time"),
                    "transport_service": basic_info.get("transport_service", self.TRANSPORT_NOT_PROVIDED),
                    "transport_vehicles": basic_info.get("transport_vehicles", ""),

                    # 1. 신체활동지원
                    "hygiene_care": self.STATUS_NOT_DONE,
                    "bath_time": "-", "bath_method": "-",
                    "meal_breakfast": "-", "meal_lunch": "-", "meal_dinner": "-",
                    "toilet_care": "-",
                    "mobility_care": self.STATUS_NOT_DONE,
                    "physical_note": "",
                    "writer_phy": None,

                    # 2. 인지관리
                    "cog_support": self.STATUS_NOT_DONE, "comm_support": self.STATUS_NOT_DONE,
                    "cognitive_note": "",
                    "writer_cog": None,

                    # 3. 간호관리
                    "bp_temp": "-", "health_manage": self.STATUS_NOT_DONE,
                    "nursing_manage": self.STATUS_NOT_DONE, "emergency": self.STATUS_NOT_DONE,
                    "nursing_note": "",
                    "writer_nur": None,

                    # 4. 기능회복
                    "prog_basic": self.STATUS_NOT_DONE, "prog_activity": self.STATUS_NOT_DONE,
                    "prog_cognitive": self.STATUS_NOT_DONE, "prog_therapy": self.STATUS_NOT_DONE,
                    "prog_enhance_detail": "",
                    "functional_note": "",
                    "writer_func": None
                }

                # --- 데이터 매핑 ---
                is_absent = False
                if idx["total_time"] != -1:
                    total_val = self._get_cell(table_data, idx["total_time"], col_idx)
                    if total_val:
                        normalized_total = total_val.replace(" ", "")
                        record["total_service_time"] = normalized_total
                        if normalized_total in self.ABSENCE_TOTAL_STATUSES:
                            record["start_time"] = None
                            record["end_time"] = None
                            record["transport_service"] = self.TRANSPORT_NOT_PROVIDED
                            record["transport_vehicles"] = ""
                            is_absent = True

                if not is_absent and idx.get("transport", -1) != -1:
                    transport_cell = self._get_cell(table_data, idx["transport"], col_idx)
                    parsed_transport = self._parse_transport_cell(transport_cell)
                    if parsed_transport:
                        record["transport_service"] = parsed_transport["service"]
                        record["transport_vehicles"] = parsed_transport["vehicles"]

                if idx["time"] != -1:
                    val = self._get_cell(table_data, idx["time"], col_idx)
                    if val and "~" in val:
                        times = val.split("~")
                        record["start_time"] = times[0].strip()
                        record["end_time"] = times[1].strip()

                if idx["hygiene"] != -1: record["hygiene_care"] = self._check_status(self._get_cell(table_data, idx["hygiene"], col_idx))

                b_time = self._get_cell(table_data, idx["bath_time"], col_idx) if idx["bath_time"] != -1 else ""
                b_method = self._get_cell(table_data, idx["bath_method"], col_idx) if idx["bath_method"] != -1 else ""

                if (not b_time or b_time == "-") and (not b_method or b_method == "-"):
                    record["bath_time"] = "없음"
                    record["bath_method"] = ""
                else:
                    record["bath_time"] = b_time
                    record["bath_method"] = b_method

                if idx["meal_bk"] != -1: record["meal_breakfast"] = self._get_cell(table_data, idx["meal_bk"], col_idx)
                if idx["meal_ln"] != -1: record["meal_lunch"] = self._get_cell(table_data, idx["meal_ln"], col_idx)
                if idx["meal_dn"] != -1: record["meal_dinner"] = self._get_cell(table_data, idx["meal_dn"], col_idx)

                if idx["excretion"] != -1: record["toilet_care"] = self._get_cell(table_data, idx["excretion"], col_idx)
                if idx["mobility"] != -1: record["mobility_care"] = self._check_status(self._get_cell(table_data, idx["mobility"], col_idx))

                if idx["cog_sup"] != -1: record["cog_support"] = self._check_status(self._get_cell(table_data, idx["cog_sup"], col_idx))
                if idx["comm_sup"] != -1: record["comm_support"] = self._check_status(self._get_cell(table_data, idx["comm_sup"], col_idx))
                if idx["bp_temp"] != -1: record["bp_temp"] = self._get_cell(table_data, idx["bp_temp"], col_idx)
                if idx["health"] != -1: record["health_manage"] = self._check_status(self._get_cell(table_data, idx["health"], col_idx))
                if idx["nursing"] != -1: record["nursing_manage"] = self._check_status(self._get_cell(table_data, idx["nursing"], col_idx))
                if idx["emergency"] != -1: record["emergency"] = self._check_status(self._get_cell(table_data, idx["emergency"], col_idx))

                if idx["prog_basic"] != -1: record["prog_basic"] = self._check_status(self._get_cell(table_data, idx["prog_basic"], col_idx))
                if idx["prog_act"] != -1: record["prog_activity"] = self._check_status(self._get_cell(table_data, idx["prog_act"], col_idx))
                if idx["prog_cog"] != -1: record["prog_cognitive"] = self._check_status(self._get_cell(table_data, idx["prog_cog"], col_idx))
                if idx["prog_ther"] != -1: record["prog_therapy"] = self._check_status(self._get_cell(table_data, idx["prog_ther"], col_idx))
                if idx["prog_detail"] != -1:
                    record["prog_enhance_detail"] = self._pick_nearby_text(table_data, idx["prog_detail"], col_idx, window=8)

                if idx["note_phy"] != -1: record["physical_note"] = self._get_cell(table_data, idx["note_phy"], col_idx)
                if idx["note_cog"] != -1: record["cognitive_note"] = self._get_cell(table_data, idx["note_cog"], col_idx)
                if idx["note_nur"] != -1: record["nursing_note"] = self._get_cell(table_data, idx["note_nur"], col_idx)
                if idx["note_func"] != -1: record["functional_note"] = self._get_cell(table_data, idx["note_func"], col_idx)

                if idx["writer_phy"] != -1: record["writer_phy"] = self._get_cell(table_data, idx["writer_phy"], col_idx)
                if idx["writer_cog"] != -1: record["writer_cog"] = self._get_cell(table_data, idx["writer_cog"], col_idx)
                if idx["writer_nur"] != -1: record["writer_nur"] = self._get_cell(table_data, idx["writer_nur"], col_idx)
                if idx["writer_func"] != -1: record["writer_func"] = self._get_cell(table_data, idx["writer_func"], col_idx)

                self.parsed_data.append(record)

    def _parse_appendix_table(self, table, category):
        """
        category: 'phy' (신체), 'nur' (간호), 'func' (기능)
        별지 데이터를 파싱하여 self.appendix_notes에 {날짜: {카테고리: 내용}} 형태로 저장
        """
        last_seen_date = None

        for row in table:
            try:
                # 첫 번째 열과 두 번째 열 가져오기
                if len(row) < 2: continue
                col1, col2 = row[0], row[1]

                raw_date = str(col1).strip() if col1 else ""
                content = str(col2).strip() if col2 else ""

                # 날짜 파싱
                current_date = None
                if re.match(r'\d{4}[\.-]\d{2}[\.-]\d{2}', raw_date):
                    current_date = raw_date.replace(".", "-").strip()
                    last_seen_date = current_date # 날짜 갱신
                elif not raw_date and content and last_seen_date:
                    # 날짜 셀이 병합되어 비어있지만 내용은 있는 경우, 직전 날짜 사용
                    current_date = last_seen_date

                if not current_date or not content:
                    continue

                # 내용 정제
                clean_content = content.replace("\n", " ").strip()

                # 저장 구조: { '2025-11-05': { 'phy': '...', 'nur': '...' } }
                if current_date not in self.appendix_notes:
                    self.appendix_notes[current_date] = {}

                if category in self.appendix_notes[current_date]:
                    self.appendix_notes[current_date][category] += " / " + clean_content
                else:
                    self.appendix_notes[current_date][category] = clean_content

            except Exception as e:
                if self._debug: print(f"[PARSER_ERR] Appendix parse error: {e}")
                continue

    def _merge_appendix_to_main(self):
        # [수정] 'cog' -> 'cognitive_note' 매핑 추가
        mapping = {
            'phy': ['physical_note'],
            'nur': ['nursing_note'],
            'func': ['functional_note', 'prog_enhance_detail'],
            'cog': ['cognitive_note']
        }

        for record in self.parsed_data:
            r_date = record['date']

            # 해당 날짜에 별지 데이터가 있는지 확인
            if r_date in self.appendix_notes:
                day_notes = self.appendix_notes[r_date] # { 'phy': '...', 'cog': '...' }

                # 각 카테고리(phy, nur, func, cog)별로 순회
                for category, target_fields in mapping.items():
                    note_content = day_notes.get(category)

                    if note_content:
                        for field in target_fields:
                            # 해당 필드에 '별지' 관련 문구가 있으면 덮어쓰기
                            if self._is_placeholder(record[field]):
                                record[field] = note_content

            # 별지 처리 후에도 여전히 '별지첨부'만 남아있는 경우 처리
            all_target_fields = ['physical_note', 'nursing_note', 'functional_note', 'cognitive_note']
            for field in all_target_fields:
                if self._is_placeholder(record[field]):
                    # 데이터는 없는데 별지라고 써있으면 경고 표시
                    record[field] += " (⚠️별지 내용 미발견)"

    def _is_appendix_table(self, table):
        """ 테이블 행 중에 날짜(YYYY.MM.DD) 형식의 데이터가 포함되어 있으면 별지로 간주 """
        if not table:
            return False
        for row in table:
            if len(row) < 2: continue
            first_col = str(row[0]).strip()
            # 2025.11.14 또는 2025-11-14 형식 체크
            if re.match(r'\d{4}[\.-]\d{2}[\.-]\d{2}', first_col):
                return True
        return False

    def _find_row_indices(self, table):
        idx = {
            "date": -1, "time": -1, "total_time": -1,
            "hygiene": -1, "bath_time": -1, "bath_method": -1,
            "meal_bk": -1, "meal_ln": -1, "meal_dn": -1,
            "excretion": -1, "mobility": -1,
            "transport": -1,
            "note_phy": -1, "writer_phy": -1,
            "cog_sup": -1, "comm_sup": -1, "note_cog": -1, "writer_cog": -1,
            "bp_temp": -1, "health": -1, "nursing": -1, "emergency": -1, "note_nur": -1, "writer_nur": -1,
            "prog_basic": -1, "prog_act": -1, "prog_cog": -1, "prog_ther": -1, "prog_detail": -1, "note_func": -1, "writer_func": -1
        }
        note_rows, writer_rows = [], []
        for i, row in enumerate(table):
            label = "".join([str(c).replace("\n", "").replace(" ", "") for c in row[:3] if c])
            normalized_label = label.replace("ㆍ", "").replace("·", "")
            normalized_row = self._normalize_row_text(row)

            if "년월/일" in label: idx["date"] = i
            elif "시작시간" in label: idx["time"] = i
            elif "총시간" in label: idx["total_time"] = i

            # 신체
            elif "세면" in label: idx["hygiene"] = i
            elif "소요시간" in label: idx["bath_time"] = i
            elif "목욕" in label and "방법" in label: idx["bath_method"] = i
            elif "아침" in label: idx["meal_bk"] = i
            elif "점심" in label: idx["meal_ln"] = i
            elif "저녁" in label: idx["meal_dn"] = i
            elif "화장실" in label or "기저귀" in label: idx["excretion"] = i
            elif "이동도움" in label: idx["mobility"] = i
            elif "이동서비스" in label: idx["transport"] = i

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
            elif ("신체" in label and "인지기능" in label and "향상" in label and "프로그램" in label) or ("신체인지기능향상프로그램" in normalized_row):
                idx["prog_detail"] = i
            elif ("인지기능" in label and "향상" in label and "훈련" in label) or ("인지기능향상훈련" in normalized_row):
                idx["prog_cog"] = i
            elif "물리" in label: idx["prog_ther"] = i
            elif "신체인지기능향상프로그램" in normalized_label and ("항목" in normalized_label or "내용" in normalized_label):
                idx["prog_detail"] = i
            elif "신체인지기능향상프로그램" in normalized_row and ("항목" in normalized_row or "내용" in normalized_row):
                idx["prog_detail"] = i
            elif "신체인지기능향상프로그램" in normalized_label:
                idx["prog_detail"] = i
            elif "신체인지기능향상프로그램" in normalized_row:
                idx["prog_detail"] = i
            elif "향상프로그램" in normalized_row and ("항목" in normalized_row or "내용" in normalized_row):
                idx["prog_detail"] = i
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

    def _parse_personal_info(self, pages):
        if not pages:
            return {}
        try:
            raw_text = pages[0].extract_text() or ""
        except Exception:
            return {}

        text = re.sub(r"\s+", " ", raw_text)
        info = {}

        def _extract(pattern):
            match = re.search(pattern, text)
            return match.group(1).strip() if match else ""

        info["customer_name"] = _extract(r"수급자명\s+([^\s]+)")

        birth = _extract(r"생년월일\s+(\d{4}\.\d{2}\.\d{2})")
        if birth:
            info["birth_date"] = birth.replace(".", "-")

        info["care_grade"] = _extract(r"장기요양등급\s+([^\s]+)")
        info["recognition_no"] = _extract(r"장기요양인정번호\s+([A-Z0-9]+)")

        facility = _extract(r"장기요양기관명\s+(.+?)\s+장기요양기관기호")
        if facility:
            info["facility_name"] = facility
        info["facility_code"] = _extract(r"장기요양기관기호\s+([0-9A-Za-z]+)")

        return info

    def _parse_basic_info_block(self, pages):
        anchor = "신체활동지원"
        block = ""

        for page in pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            if not text:
                continue

            if anchor in text:
                block += text.split(anchor)[0]
                break
            else:
                block += text + "\n"

        if not block:
            return {}

        info = {}

        total_match = re.search(r"총\s*시간[:\s]*([0-9]{1,4}\s*분|미이용|결석)", block)
        if total_match:
            info["total_service_time"] = total_match.group(1).replace(" ", "")

        time_match = re.search(
            r"시작\s*시간\s*~\s*종료\s*시간[:\s]*([0-9]{1,2}:[0-9]{2})\s*[~\-]\s*([0-9]{1,2}:[0-9]{2})",
            block
        )
        if not time_match:
            time_match = re.search(
                r"시작\s*시간[:\s]*([0-9]{1,2}:[0-9]{2}).*?종료\s*시간[:\s]*([0-9]{1,2}:[0-9]{2})",
                block,
                re.S
            )
        if time_match:
            info["start_time"] = time_match.group(1)
            info["end_time"] = time_match.group(2)

        transport_match = re.search(
            r"이동\s*서비스\s*제공\s*여부[^\n]*?(?:[:：]\s*|)([^\n]*)",
            block
        )
        raw_transport = (transport_match.group(1).strip() if transport_match and transport_match.group(1) else "")

        vehicle_match = re.search(r"\(차량번호\)\s*([^\n]+)", block)
        vehicle_line = vehicle_match.group(1) if vehicle_match else ""
        cleaned_vehicle_line = re.sub(r"[^\d가-힣, ]", " ", vehicle_line)
        plates = re.findall(r"\d{2,3}[가-힣]\d{4}", cleaned_vehicle_line)

        if plates:
            unique = list(dict.fromkeys(plates))
            info["transport_vehicles"] = ", ".join(unique)

        if raw_transport or plates:
            provided = "■" in raw_transport
            info["transport_service"] = self.TRANSPORT_PROVIDED if provided else self.TRANSPORT_NOT_PROVIDED

        return info

    def _parse_transport_cell(self, cell_value):
        if not cell_value:
            return None

        raw = str(cell_value).strip()
        if not raw:
            return None

        provided = "■" in raw
        cleaned = re.sub(r"[^\d가-힣, ]", " ", raw)
        plates = re.findall(r"\d{2,3}[가-힣]\d{4}", cleaned)
        vehicles = ", ".join(dict.fromkeys(plates)) if plates else ""

        return {
            "service": self.TRANSPORT_PROVIDED if provided else self.TRANSPORT_NOT_PROVIDED,
            "vehicles": vehicles
        }

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