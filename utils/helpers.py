import re
import random
import string
from datetime import date, datetime

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

from werkzeug.security import generate_password_hash
from models import db
from utils.email_service import send_credentials_email
from utils.mongo_client import get_mongo_db


# ---------- AGE ----------
def calculate_age(dob: date) -> int:
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


# ---------- EMPLOYEE ID (DICT001..DICT010) ----------
def generate_employee_id() -> str:
    """
    Generates a new Employee ID for DICT department.
    Format: DICT001, DICT002, ... DICT010
    Maximum 10 employees allowed in DICT.
    """
    from models.employee import Employee  # local import to avoid circular

    existing = Employee.query.filter_by(department="DICT").all()
    if len(existing) >= 10:
        raise ValueError("Maximum 10 employees allowed for DICT department.")

    used_numbers = []
    for emp in existing:
        if emp.employee_id and emp.employee_id.startswith("DICT"):
            try:
                num = int(emp.employee_id[4:])
                used_numbers.append(num)
            except ValueError:
                continue

    next_number = 1
    while next_number in used_numbers:
        next_number += 1

    return f"DICT{next_number:03d}"


# ---------- RANDOM PASSWORD ----------
def generate_random_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choice(chars) for _ in range(length))


# ---------- AADHAAR VALIDATION ----------
def validate_aadhaar(aadhaar: str) -> bool:
    """
    Aadhaar must be exactly 12 digits.
    """
    return bool(re.fullmatch(r"\d{12}", aadhaar))


# ---------- PAN VALIDATION ----------
def validate_pan(pan: str, last_name_first_letter: str | None = None) -> bool:
    """
    PAN format:
    - 1st–3rd: letters
    - 4th: type (P, C, H, F, A, T, B, G, L, J)
    - 5th: first letter of surname for individuals (type P)
    - 6th–9th: digits
    - 10th: letter
    """
    pan = pan.upper()

    # Basic pattern: 5 letters, 4 digits, 1 letter
    if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan):
        return False

    # 4th char - type
    valid_types = set("PCHFATBGLJ")
    if pan[3] not in valid_types:
        return False

    # For individuals (P), 5th letter should match surname first letter (if provided)
    if pan[3] == "P" and last_name_first_letter:
        if pan[4] != last_name_first_letter.upper():
            return False

    return True


# ---------- PASSWORD RESET TOKEN HELPERS ----------
def _get_serializer() -> URLSafeTimedSerializer:
    """
    Internal helper to get a configured URLSafeTimedSerializer.
    """
    secret_key = current_app.config["SECRET_KEY"]
    return URLSafeTimedSerializer(secret_key, salt="uap-password-reset")


def generate_reset_token(user_id: int, role: str = "hsd") -> str:
    """
    Generate a signed token for password reset.
    Payload: { "user_id": <int>, "role": <str> }
    """
    s = _get_serializer()
    return s.dumps({"user_id": user_id, "role": role})


def verify_reset_token(token: str, max_age: int = 3600):
    """
    Verify password reset token. Returns payload dict or None.
    max_age in seconds (default: 1 hour).
    """
    s = _get_serializer()
    try:
        data = s.loads(token, max_age=max_age)
        return data
    except SignatureExpired:
        print("Reset token expired.")
        return None
    except BadSignature:
        print("Invalid reset token.")
        return None


# ---------- MONGO REGISTRATION NUMBER GENERATORS ----------
def generate_student_registration_number() -> str:
    """
    Generate next student registration number using MongoDB.

    Example:
      last: UAP25999 -> next: UAP26000

    If none exists:
      start from UAP<YY001>, e.g. UAP25001 for 2025.
    """
    db_mongo = get_mongo_db()
    students = db_mongo["students"]

    prefix = "UAP"

    last = students.find_one(
        {"registration_number": {"$regex": f"^{prefix}"}},
        sort=[("_id", -1)]
    )

    if not last or not str(last.get("registration_number", "")).startswith(prefix):
        year_suffix = str(date.today().year)[-2:]   # '25' for 2025
        start_num = int(f"{year_suffix}001")        # 25001
        return f"{prefix}{start_num}"

    reg = last["registration_number"]
    numeric_part = int(reg[len(prefix):])
    next_num = numeric_part + 1
    return f"{prefix}{next_num:05d}"


def generate_teacher_registration_number() -> str:
    """
    Generate next teacher registration number using MongoDB.
    """
    db_mongo = get_mongo_db()
    teachers = db_mongo["teachers"]

    prefix = "UAP"

    last = teachers.find_one(
        {"registration_number": {"$regex": f"^{prefix}"}},
        sort=[("_id", -1)]
    )

    if not last or not str(last.get("registration_number", "")).startswith(prefix):
        year_suffix = str(date.today().year)[-2:]
        start_num = int(f"{year_suffix}001")
        return f"{prefix}{start_num}"

    reg = last["registration_number"]
    numeric_part = int(reg[len(prefix):])
    next_num = numeric_part + 1
    return f"{prefix}{next_num:05d}"


# ---------- MONGO ROLL NUMBER GENERATOR (DEPARTMENT-BASED) ----------
def generate_student_roll_number(department: str, session_start_year: int) -> str:
    """
    Roll number is department + session_start_year + running number.
    Example: CSE2025-001, CSE2025-002 ...
    """
    db_mongo = get_mongo_db()
    students = db_mongo["students"]

    dept_norm = department.upper().replace(" ", "")
    base_prefix = f"{dept_norm}{session_start_year}"

    last = students.find_one(
        {
            "department": dept_norm,
            "session_start_year": session_start_year,
            "roll_number": {"$regex": f"^{base_prefix}"},
        },
        sort=[("roll_number", -1)]
    )

    if not last:
        seq = 1
    else:
        try:
            seq_part = last["roll_number"].split("-")[-1]
            seq = int(seq_part) + 1
        except Exception:
            seq = 1

    return f"{base_prefix}-{seq:03d}"


# ---------- CREATE EMPLOYEE FROM DATA ----------
def create_employee_from_data(data: dict):
    """
    data expected keys:
    name, email, contact_number, dob (YYYY-MM-DD),
    department, aadhaar_number, pan_number,
    profile_photo (optional), date_of_joining (YYYY-MM-DD),
    address
    """
    from models.employee import Employee  # local import

    # 1) Validate Aadhaar
    aadhaar = data["aadhaar_number"].strip()
    if not validate_aadhaar(aadhaar):
        raise ValueError("Invalid Aadhaar number. Must be 12 digits.")

    # 2) Validate PAN
    pan = data["pan_number"].strip().upper()
    name_parts = data["name"].strip().split()
    surname_letter = name_parts[-1][0] if name_parts else None
    if not validate_pan(pan, surname_letter):
        raise ValueError("Invalid PAN number format or mismatch with surname.")

    # 3) Parse dates
    dob = datetime.strptime(data["dob"], "%Y-%m-%d").date()
    doj = datetime.strptime(data["date_of_joining"], "%Y-%m-%d").date()

    # 4) Calculate age
    age = calculate_age(dob)

    # 5) Generate Employee ID and password
    employee_id = generate_employee_id()
    plain_password = generate_random_password()
    password_hash = generate_password_hash(plain_password)

    department = data.get("department", "DICT").strip() or "DICT"

    emp = Employee(
        employee_id=employee_id,
        password_hash=password_hash,
        name=data["name"].strip(),
        email=data["email"].strip(),
        contact_number=data["contact_number"].strip(),
        dob=dob,
        age=age,
        department=department,
        aadhaar_number=aadhaar,
        pan_number=pan,
        profile_photo=data.get("profile_photo") or None,
        date_of_joining=doj,
        address=data["address"].strip(),
    )

    db.session.add(emp)
    db.session.commit()

    # 6) Send credentials email AFTER commit
    sent = send_credentials_email(emp.email, emp.employee_id, plain_password, emp.name)

    if not sent:
        print(f"⚠ Employee {emp.employee_id} created, BUT email failed to send.")
    else:
        print(f"📧 Credentials email sent to {emp.email}")

    # DEV ONLY: show password in terminal so you don't lose it
    print(f"TEMP DEV PASSWORD for {emp.employee_id}: {plain_password}")

    return emp
