# db.py
# Postgres-backed storage (Supabase) for students, parents, and routed issues.
# Uses psycopg2. Connection comes from DATABASE_URL in .env.

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """Create tables if they don't exist yet. Safe to call every startup.
    This is a fresh database, so unlike the old local SQLite setup, no
    migration logic is needed — the schema is created correct from the start."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            student_name TEXT NOT NULL,
            grade TEXT,
            attendance TEXT,
            exam_schedule TEXT,
            fee_status TEXT,
            roll_number TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parents (
            id SERIAL PRIMARY KEY,
            whatsapp_number TEXT NOT NULL,
            student_id INTEGER NOT NULL REFERENCES students(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            parent_phone TEXT NOT NULL,
            student_id INTEGER,
            message_text TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            exam_name TEXT NOT NULL,
            marks TEXT,
            percentage TEXT,
            grade TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, exam_name)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def add_student_row(parent_phone, student_name, grade, attendance, exam_schedule, fee_status, roll_number=None):
    """Inserts a new student + links their parent's number. Returns the new
    student's id, or None if the parent link failed to insert."""
    clean_phone = parent_phone.replace("+", "").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO students (student_name, grade, attendance, exam_schedule, fee_status, roll_number) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (student_name, grade, attendance, exam_schedule, fee_status, roll_number or None),
    )
    student_id = cur.fetchone()["id"]

    try:
        cur.execute(
            "INSERT INTO parents (whatsapp_number, student_id) VALUES (%s, %s)",
            (clean_phone, student_id),
        )
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"Failed to link parent {clean_phone}: {e}")
        return None

    conn.commit()
    cur.close()
    conn.close()
    return student_id


def get_students_by_phone(phone: str):
    """
    Looks up ALL students linked to a parent's WhatsApp number — a parent
    can have more than one child registered under the same number.
    Returns a list of dicts (empty list if the number isn't registered).
    Each student dict also includes a "marks" list — one entry per exam
    recorded for them (FA1, FA2, SA1, etc.), most recent first.
    """
    clean_phone = phone.replace("+", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.roll_number, s.student_name, s.grade, s.attendance, s.exam_schedule, s.fee_status
        FROM parents p
        JOIN students s ON p.student_id = s.id
        WHERE p.whatsapp_number = %s
        ORDER BY s.id
    """, (clean_phone,))
    rows = cur.fetchall()

    students = []
    for row in rows:
        student = dict(row)
        cur.execute("""
            SELECT exam_name, marks, percentage, grade
            FROM marks
            WHERE student_id = %s
            ORDER BY recorded_at DESC
        """, (student["id"],))
        student["marks"] = [dict(m) for m in cur.fetchall()]
        students.append(student)

    cur.close()
    conn.close()
    return students


def find_student_by_name_and_phone(student_name: str, parent_phone: str):
    """Finds an existing student by matching BOTH their name and their
    parent's WhatsApp number (case-insensitive on name)."""
    clean_phone = parent_phone.replace("+", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*
        FROM parents p
        JOIN students s ON p.student_id = s.id
        WHERE p.whatsapp_number = %s AND LOWER(s.student_name) = LOWER(%s)
    """, (clean_phone, student_name.strip()))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def update_student_fields(student_id: int, grade: str = None, attendance: str = None):
    """Updates a student's grade/attendance in place."""
    conn = get_connection()
    cur = conn.cursor()
    if grade is not None:
        cur.execute("UPDATE students SET grade = %s WHERE id = %s", (grade, student_id))
    if attendance is not None:
        cur.execute("UPDATE students SET attendance = %s WHERE id = %s", (attendance, student_id))
    conn.commit()
    cur.close()
    conn.close()


def upsert_marks_by_student_id(student_id: int, exam_name: str, marks: str = None, percentage: str = None, grade: str = None):
    """Adds or updates a student's marks for a specific exam, matched by student_id directly."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO marks (student_id, exam_name, marks, percentage, grade)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (student_id, exam_name)
        DO UPDATE SET marks = EXCLUDED.marks,
                       percentage = EXCLUDED.percentage,
                       grade = EXCLUDED.grade,
                       recorded_at = CURRENT_TIMESTAMP
    """, (student_id, exam_name, marks, percentage, grade))
    conn.commit()
    cur.close()
    conn.close()


def get_student_by_roll_number(roll_number: str):
    """Finds a single student by their school-assigned roll number."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE roll_number = %s", (str(roll_number).strip(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def upsert_marks(roll_number: str, exam_name: str, marks: str = None, percentage: str = None, grade: str = None):
    """Adds or updates a student's marks for a specific exam, matched by roll_number.
    Returns True if a student was found and marks were recorded, False otherwise."""
    student = get_student_by_roll_number(roll_number)
    if not student:
        return False
    upsert_marks_by_student_id(student["id"], exam_name, marks, percentage, grade)
    return True


def log_issue(parent_phone: str, message_text: str, student_id: int = None):
    """Stores a parent-raised issue for school management to review later."""
    clean_phone = parent_phone.replace("+", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO issues (parent_phone, student_id, message_text) VALUES (%s, %s, %s)",
        (clean_phone, student_id, message_text),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_open_issues():
    """Returns all open issues, most recent first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM issues WHERE status = 'open' ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def resolve_issue(issue_id: int):
    """Marks a single issue as resolved. Returns True if a row was updated."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE issues SET status = 'resolved' WHERE id = %s", (issue_id,))
    updated = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return updated


def delete_student(student_id: int):
    """Removes a student and everything linked to them (parent link, marks)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT student_name FROM students WHERE id = %s", (student_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None

    name = row["student_name"]
    cur.execute("DELETE FROM marks WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM parents WHERE student_id = %s", (student_id,))
    cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
    conn.commit()
    cur.close()
    conn.close()
    return name


# Ensure tables exist as soon as this module is imported.
init_db()