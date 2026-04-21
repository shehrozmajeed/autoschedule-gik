import csv
import re
import os
import pandas as pd
from typing import List, Tuple
from core.models import Course, Room, TimeSlot

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


# ─── Static data loaders ──────────────────────────────────────────────────────

def load_rooms() -> List[Room]:
    rooms = []
    path = os.path.join(DATA_DIR, 'rooms.csv')
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rooms.append(Room(
                room_id=row['room_id'],
                room_name=row['room_name'],
                building=row['building'],
                room_type=row['type'],
                capacity=int(row['capacity'])
            ))
    return rooms


def load_timeslots() -> List[TimeSlot]:
    slots = []
    path = os.path.join(DATA_DIR, 'timeslots.csv')
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            slots.append(TimeSlot(
                slot_id=row['slot_id'],
                day=row['day'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                slot_index=int(row['slot_index']),
                day_type=row['day_type']
            ))
    return slots


# ─── Course parsing helpers ───────────────────────────────────────────────────

def _clean(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', '-') else s


def _detect_type(code: str, title: str) -> str:
    """
    Determine if a course is a lab or lecture.
    Labs are identified by:
      - Course code ending with 'L'  (e.g. CS101L, AI321L, IF101L)
      - Title containing 'lab'
    """
    code_upper = code.upper().strip()
    # Match codes like CS101L, AI321L, CYS451L — ends with digit(s) then L
    if re.search(r'\d+L$', code_upper):
        return 'lab'
    if 'lab' in title.lower():
        return 'lab'
    return 'lecture'


def _build_course(row: dict) -> 'Course | None':
    # Try multiple possible column name variants
    def get(*keys):
        for k in keys:
            for col in row:
                if col.strip().lower() == k.lower():
                    v = _clean(row[col])
                    if v:
                        return v
        return ''

    code      = get('code', 'Code', 'CODE', 'course_code')
    section   = get('section', 'Section', 'Sec', 'SEC', 'sec')
    title     = get('title', 'Title', 'course title', 'Course Title', 'course_title', 'TITLE')
    instructor= get('instructor', 'Instructor', 'Course Instructor', 'INSTRUCTOR', 'Faculty')
    program   = get('program', 'Program', 'For', 'FOR', 'Department', 'dept')

    try:
        ch = int(float(get('credit_hours', 'CHs', 'CHS', 'Credits', 'CH', 'credit hours')))
    except:
        ch = 3

    try:
        cap = int(float(get('capacity', 'Capacity', 'Exp Nos', 'Expected', 'EXP', 'students')))
    except:
        cap = 50

    if not code or not title:
        return None

    ctype = _detect_type(code, title)

    return Course(
        code=code,
        section=section,
        title=title,
        credit_hours=ch,
        course_type=ctype,
        instructor=instructor or 'TBA',
        program=program or 'GEN',
        capacity=cap,
    )


# ─── File parsers ─────────────────────────────────────────────────────────────

def _dedup(courses: List[Course]) -> List[Course]:
    seen = set()
    out = []
    for c in courses:
        if c.key not in seen:
            seen.add(c.key)
            out.append(c)
    return out


def parse_csv_file(filepath: str) -> Tuple[List[Course], List[str]]:
    courses, warnings = [], []
    try:
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                c = _build_course(dict(row))
                if c:
                    courses.append(c)
    except Exception as e:
        warnings.append(f"CSV error: {e}")
    return _dedup(courses), warnings


def parse_excel(filepath: str) -> Tuple[List[Course], List[str]]:
    courses, warnings = [], []
    try:
        xl = pd.ExcelFile(filepath)
        for sheet_name in xl.sheet_names:
            try:
                df = xl.parse(sheet_name, dtype=str)
                df = df.where(pd.notnull(df), None)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    c = _build_course(row.to_dict())
                    if c:
                        courses.append(c)
            except Exception as e:
                warnings.append(f"Sheet '{sheet_name}' error: {e}")
    except Exception as e:
        warnings.append(f"Excel error: {e}")
    return _dedup(courses), warnings


def parse_pdf(filepath: str) -> Tuple[List[Course], List[str]]:
    courses, warnings = [], []
    try:
        import pdfplumber
    except ImportError:
        warnings.append("pdfplumber not installed. Run: pip install pdfplumber")
        return courses, warnings

    try:
        with pdfplumber.open(filepath) as pdf:
            found_header = False
            headers = []
            all_data_rows = []

            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for i, row in enumerate(table):
                        if row is None:
                            continue
                        cells = [str(c).strip() if c else '' for c in row]
                        if not found_header:
                            low = [c.lower() for c in cells]
                            if any('code' in x or 'course' in x for x in low):
                                headers = cells
                                found_header = True
                                all_data_rows.extend(table[i+1:])
                                break
                        else:
                            all_data_rows.extend(table)
                            break

            if found_header and headers:
                for row in all_data_rows:
                    if not row or not any(row):
                        continue
                    cells = [str(c).strip() if c else '' for c in row]
                    row_dict = {headers[j]: cells[j] for j in range(min(len(headers), len(cells)))}
                    c = _build_course(row_dict)
                    if c:
                        courses.append(c)
            else:
                warnings.append("Table detection failed, trying text extraction.")
                courses, w2 = _parse_pdf_text(pdf)
                warnings.extend(w2)

    except Exception as e:
        warnings.append(f"PDF error: {e}")

    return _dedup(courses), warnings


def _parse_pdf_text(pdf) -> Tuple[List[Course], List[str]]:
    """Regex-based fallback for GIK-style PDFs."""
    courses, warnings = [], []
    pattern = re.compile(
        r'^([A-Z]{2,4}\d{3,4}L?)\s+([A-Z0-9]+)\s+(.+?)\s+(\d)\s+(.+?)\s+'
        r'(BAI|BCS|BCE|BDS|CYS|SE|BME|CVE|CME|BEE\w*|EEE\w*|MGS\w*|BES|MTE\w*)\s+(\d+)\s*$'
    )
    for page in pdf.pages:
        text = page.extract_text() or ''
        for line in text.split('\n'):
            m = pattern.match(line.strip())
            if m:
                code, sec, title, ch, instr, prog, cap = m.groups()
                c = Course(
                    code=code.strip(), section=sec.strip(), title=title.strip(),
                    credit_hours=int(ch),
                    course_type=_detect_type(code, title),
                    instructor=instr.strip(), program=prog.strip(), capacity=int(cap)
                )
                courses.append(c)
    return courses, warnings


def parse_file(filepath: str) -> Tuple[List[Course], List[str]]:
    """Auto-detect file format and parse."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return parse_pdf(filepath)
    elif ext in ('.xlsx', '.xls', '.xlsm', '.ods'):
        return parse_excel(filepath)
    elif ext == '.csv':
        return parse_csv_file(filepath)
    else:
        return [], [f"Unsupported file type: '{ext}'. Use PDF, XLSX, or CSV."]
