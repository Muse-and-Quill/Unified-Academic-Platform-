from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import os
import pandas as pd

from utils.helpers import (
    generate_reset_token,
    verify_reset_token,
    generate_student_registration_number,
    generate_teacher_registration_number,
    generate_student_roll_number,
)
from utils.email_service import (
    send_reset_password_email,
    send_student_credentials_email,
    send_teacher_credentials_email,
)
from utils.mongo_client import get_mongo_db

from models.employee import Employee
from models import db


auth_bp = Blueprint("auth_bp", __name__)


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in {"csv", "xlsx", "xls"}


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # GET -> show login page
    if request.method == "GET":
        return render_template("login.html", error=None)

    # POST -> process form
    role = request.form.get("role")          # hsd / student / teacher (for future)
    employee_id = request.form.get("employee_id", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    error = None

    # For now we only implement HSD / DICT employee login
    if role != "hsd":
        error = "Only HSD / DICT employee login is enabled right now."
        return render_template("login.html", error=error)

    # Find employee
    emp = Employee.query.filter_by(
        employee_id=employee_id,
        email=email,
        is_active=True
    ).first()

    if not emp:
        error = "Invalid Employee ID or Email."
        return render_template("login.html", error=error)

    # Check password
    if not check_password_hash(emp.password_hash, password):
        error = "Incorrect password."
        return render_template("login.html", error=error)

    # Login success -> save in session
    session["user_id"] = emp.id
    session["user_role"] = "hsd"
    session["employee_id"] = emp.employee_id
    session["user_name"] = emp.name

    # Redirect to DICT / HSD dashboard
    return redirect(url_for("auth_bp.dict_dashboard"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_bp.login"))


@auth_bp.route("/dict/dashboard")
def dict_dashboard():
    # Simple session protection
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    student_count = db_mongo["students"].count_documents({})
    teacher_count = db_mongo["teachers"].count_documents({})

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        employee_id=session.get("employee_id"),
        student_count=student_count,
        teacher_count=teacher_count,
    )


@auth_bp.route("/dict/upload/students", methods=["POST"])
def upload_students():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    file = request.files.get("student_file")
    department = request.form.get("student_department", "").strip()
    category = request.form.get("student_category", "").strip()
    label = request.form.get("student_label", "").strip()
    session_start_year = request.form.get("student_session_start_year")
    session_end_year = request.form.get("student_session_end_year")

    if not file or file.filename == "":
        flash("Please select a student file.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not _allowed_file(file.filename):
        flash("Only CSV or Excel files are allowed for students.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not department or not session_start_year or not session_end_year:
        flash("Department and session years are required for students.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    session_start_year = int(session_start_year)
    session_end_year = int(session_end_year)

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        print("Error reading student file:", e)
        flash("Could not read the student file. Check format.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    required_cols = {"name", "email"}
    lowered_cols = {c.lower(): c for c in df.columns}
    if not required_cols.issubset(set(lowered_cols.keys())):
        flash("Student file must have at least 'name' and 'email' columns.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    created_count = 0

    for _, row in df.iterrows():
        name = str(row.get(lowered_cols["name"]) or "").strip()
        email = str(row.get(lowered_cols["email"]) or "").strip()
        phone_col = lowered_cols.get("phone")
        phone = str(row.get(phone_col) or "").strip() if phone_col else ""

        if not name or not email:
            continue

        reg_no = generate_student_registration_number()
        roll_no = generate_student_roll_number(department, session_start_year)

        plain_password = f"Welcome@{reg_no}"
        password_hash = generate_password_hash(plain_password)

        dept_norm = department.upper().replace(" ", "")

        doc = {
            "registration_number": reg_no,
            "roll_number": roll_no,
            "name": name,
            "email": email,
            "phone": phone or None,
            "department": dept_norm,
            "category": category or None,
            "label": label or None,
            "session_start_year": session_start_year,
            "session_end_year": session_end_year,
            "password_hash": password_hash,
            "is_active": True,
        }

        students_collection.insert_one(doc)

        send_student_credentials_email(
            to_email=email,
            registration_number=reg_no,
            roll_number=roll_no,
            plain_password=plain_password,
            name=name,
        )

        created_count += 1

    flash(f"Successfully created {created_count} student accounts in MongoDB.", "success")
    return redirect(url_for("auth_bp.dict_dashboard"))


@auth_bp.route("/dict/upload/teachers", methods=["POST"])
def upload_teachers():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    file = request.files.get("teacher_file")
    department = request.form.get("teacher_department", "").strip()
    session_start_year = request.form.get("teacher_session_start_year")
    session_end_year = request.form.get("teacher_session_end_year")

    if not file or file.filename == "":
        flash("Please select a teacher file.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not _allowed_file(file.filename):
        flash("Only CSV or Excel files are allowed for teachers.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not department or not session_start_year or not session_end_year:
        flash("Department and session years are required for teachers.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    session_start_year = int(session_start_year)
    session_end_year = int(session_end_year)

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        print("Error reading teacher file:", e)
        flash("Could not read the teacher file. Check format.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    required_cols = {"name", "email"}
    lowered_cols = {c.lower(): c for c in df.columns}
    if not required_cols.issubset(set(lowered_cols.keys())):
        flash("Teacher file must have at least 'name' and 'email' columns.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    created_count = 0

    for _, row in df.iterrows():
        name = str(row.get(lowered_cols["name"]) or "").strip()
        email = str(row.get(lowered_cols["email"]) or "").strip()
        phone_col = lowered_cols.get("phone")
        phone = str(row.get(phone_col) or "").strip() if phone_col else ""
        designation_col = lowered_cols.get("designation")
        designation = str(row.get(designation_col) or "").strip() if designation_col else ""

        if not name or not email:
            continue

        reg_no = generate_teacher_registration_number()
        plain_password = f"Welcome@{reg_no}"
        password_hash = generate_password_hash(plain_password)

        doc = {
            "registration_number": reg_no,
            "name": name,
            "email": email,
            "phone": phone or None,
            "department": department,
            "designation": designation or None,
            "session_start_year": session_start_year,
            "session_end_year": session_end_year,
            "password_hash": password_hash,
            "is_active": True,
        }

        teachers_collection.insert_one(doc)

        send_teacher_credentials_email(
            to_email=email,
            registration_number=reg_no,
            plain_password=plain_password,
            name=name,
            department=department,
        )

        created_count += 1

    flash(f"Successfully created {created_count} teacher accounts in MongoDB.", "success")
    return redirect(url_for("auth_bp.dict_dashboard"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        # Show a form where user enters employee_id + email
        return render_template("forgot_password.html", message=None, error=None)

    # POST: handle form submission
    role = request.form.get("role") or "hsd"
    employee_id = request.form.get("employee_id", "").strip()
    email = request.form.get("email", "").strip()

    if role != "hsd":
        # For now, only DICT/HSD employees supported
        error = "Password reset is currently enabled only for HSD / DICT employees."
        return render_template("forgot_password.html", message=None, error=error)

    # Find the employee
    emp = Employee.query.filter_by(
        employee_id=employee_id,
        email=email,
        is_active=True
    ).first()

    # For security: do not reveal whether the account exists
    if not emp:
        message = "If the details are correct, a reset link has been sent to your email."
        return render_template("forgot_password.html", message=message, error=None)

    # Generate token and send email
    token = generate_reset_token(emp.id, role="hsd")
    reset_url = url_for("auth_bp.reset_password", token=token, _external=True)

    sent = send_reset_password_email(emp.email, reset_url, emp.name)
    if not sent:
        error = "We could not send the reset email. Please contact the DICT team."
        return render_template("forgot_password.html", message=None, error=error)

    message = "If the details are correct, a reset link has been sent to your email."
    return render_template("forgot_password.html", message=message, error=None)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    # Verify token
    data = verify_reset_token(token)
    if not data or data.get("role") != "hsd":
        error = "This reset link is invalid or has expired."
        return render_template("reset_password.html", token=None, error=error, success=None)

    user_id = data["user_id"]
    emp = Employee.query.get(user_id)
    if not emp or not emp.is_active:
        error = "This account is not available."
        return render_template("reset_password.html", token=None, error=error, success=None)

    if request.method == "GET":
        # Show the form to set new password
        return render_template("reset_password.html", token=token, error=None, success=None)

    # POST: update password
    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if len(new_password) < 8:
        error = "Password must be at least 8 characters long."
        return render_template("reset_password.html", token=token, error=error, success=None)

    if new_password != confirm_password:
        error = "Passwords do not match."
        return render_template("reset_password.html", token=token, error=error, success=None)

    # Save new password
    emp.password_hash = generate_password_hash(new_password)
    db.session.commit()

    success = "Your password has been reset successfully. You can now log in with your new password."
    return render_template("reset_password.html", token=None, error=None, success=success)
