from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from flask import current_app
from werkzeug.utils import secure_filename
import os
import pandas as pd
from bson.objectid import ObjectId
import csv
from io import StringIO
from flask import Response


from utils.helpers import (
    generate_reset_token,
    verify_reset_token,
    generate_student_registration_number,
    generate_teacher_registration_number,
    generate_student_roll_number,
    generate_staff_employee_number,
    calculate_age,
)
from utils.email_service import (
    send_reset_password_email,
    send_student_credentials_email,
    send_teacher_credentials_email,
    send_staff_credentials_email,
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

    # ---------- TOTAL COUNTS ----------
    student_collection = db_mongo["students"]
    teacher_collection = db_mongo["teachers"]
    staff_collection = db_mongo["staff"]

    student_count = student_collection.count_documents({})
    teacher_count = teacher_collection.count_documents({})
    staff_count = staff_collection.count_documents({})

    # ---------- DEPARTMENT-WISE STUDENT SUMMARY ----------
    student_dept_summary = list(student_collection.aggregate([
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))

    # ---------- DEPARTMENT-WISE TEACHER SUMMARY ----------
    teacher_dept_summary = list(teacher_collection.aggregate([
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))

    # ---------- ROLE-WISE STAFF SUMMARY (Library, Canteen, etc.) ----------
    staff_role_summary = list(staff_collection.aggregate([
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))

    # ---------- CURRENT DICT EMPLOYEE (FOR PROFILE / AVATAR) ----------
    emp_id = session.get("user_id")
    emp = Employee.query.get(emp_id) if emp_id else None

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        employee_id=session.get("employee_id"),
        student_count=student_count,
        teacher_count=teacher_count,
        staff_count=staff_count,
        student_dept_summary=student_dept_summary,
        teacher_dept_summary=teacher_dept_summary,
        staff_role_summary=staff_role_summary,
        emp=emp,
    )

@auth_bp.route("/dict/export/students")
def export_students_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    cursor = students_collection.find({}, {
        "_id": 0,
        "registration_number": 1,
        "roll_number": 1,
        "name": 1,
        "email": 1,
        "contact_number": 1,
        "department": 1,
        "session_start_year": 1,
        "session_end_year": 1,
    })

    si = StringIO()
    writer = csv.writer(si)

    # header row
    writer.writerow([
        "Registration Number",
        "Roll Number",
        "Name",
        "Email",
        "Contact Number",
        "Department",
        "Session Start Year",
        "Session End Year",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("registration_number", ""),
            doc.get("roll_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("contact_number", ""),
            doc.get("department", ""),
            doc.get("session_start_year", ""),
            doc.get("session_end_year", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_uap.csv"},
    )

@auth_bp.route("/dict/export/teachers")
def export_teachers_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    cursor = teachers_collection.find({}, {
        "_id": 0,
        "registration_number": 1,
        "name": 1,
        "email": 1,
        "department": 1,
        "designation": 1,
        "session_start_year": 1,
        "session_end_year": 1,
    })

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Registration Number",
        "Name",
        "Email",
        "Department",
        "Designation",
        "Session Start Year",
        "Session End Year",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("registration_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("department", ""),
            doc.get("designation", ""),
            doc.get("session_start_year", ""),
            doc.get("session_end_year", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=teachers_uap.csv"},
    )

@auth_bp.route("/dict/export/staff")
def export_staff_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    cursor = staff_collection.find({}, {
        "_id": 0,
        "employee_number": 1,
        "name": 1,
        "email": 1,
        "contact_number": 1,
        "role": 1,
        "years_of_experience": 1,
        "date_of_joining": 1,
    })

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Employee Number",
        "Name",
        "Email",
        "Contact Number",
        "Role",
        "Years of Experience",
        "Date of Joining",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("employee_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("contact_number", ""),
            doc.get("role", ""),
            doc.get("years_of_experience", ""),
            doc.get("date_of_joining", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=staff_uap.csv"},
    )
@auth_bp.route("/dict/export/students/filtered")
def export_students_filtered_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    filters = []

    if q:
        filters.append({
            "$or": [
                {"registration_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"department": {"$regex": q, "$options": "i"}},
            ]
        })

    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    cursor = students_collection.find(query, {
        "_id": 0,
        "registration_number": 1,
        "roll_number": 1,
        "name": 1,
        "email": 1,
        "contact_number": 1,
        "department": 1,
        "session_start_year": 1,
        "session_end_year": 1,
    }).sort("registration_number", 1)

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Registration Number",
        "Roll Number",
        "Name",
        "Email",
        "Contact Number",
        "Department",
        "Session Start Year",
        "Session End Year",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("registration_number", ""),
            doc.get("roll_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("contact_number", ""),
            doc.get("department", ""),
            doc.get("session_start_year", ""),
            doc.get("session_end_year", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_filtered_uap.csv"},
    )

@auth_bp.route("/dict/export/teachers/filtered")
def export_teachers_filtered_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    filters = []

    # Search filter
    if q:
        filters.append({
            "$or": [
                {"registration_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"department": {"$regex": q, "$options": "i"}},
            ]
        })

    # Date range filter on created_at
    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    cursor = teachers_collection.find(query, {
        "_id": 0,
        "registration_number": 1,
        "name": 1,
        "email": 1,
        "department": 1,
        "designation": 1,
        "session_start_year": 1,
        "session_end_year": 1,
    }).sort("registration_number", 1)

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Registration Number",
        "Name",
        "Email",
        "Department",
        "Designation",
        "Session Start Year",
        "Session End Year",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("registration_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("department", ""),
            doc.get("designation", ""),
            doc.get("session_start_year", ""),
            doc.get("session_end_year", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=teachers_filtered_uap.csv"},
    )

@auth_bp.route("/dict/export/staff/filtered")
def export_staff_filtered_csv():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    filters = []

    # Search filter
    if q:
        filters.append({
            "$or": [
                {"employee_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"role": {"$regex": q, "$options": "i"}},
            ]
        })

    # Date range filter on created_at
    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    cursor = staff_collection.find(query, {
        "_id": 0,
        "employee_number": 1,
        "name": 1,
        "email": 1,
        "contact_number": 1,
        "role": 1,
        "years_of_experience": 1,
        "date_of_joining": 1,
    }).sort("employee_number", 1)

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow([
        "Employee Number",
        "Name",
        "Email",
        "Contact Number",
        "Role",
        "Years of Experience",
        "Date of Joining",
    ])

    for doc in cursor:
        writer.writerow([
            doc.get("employee_number", ""),
            doc.get("name", ""),
            doc.get("email", ""),
            doc.get("contact_number", ""),
            doc.get("role", ""),
            doc.get("years_of_experience", ""),
            doc.get("date_of_joining", ""),
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=staff_filtered_uap.csv"},
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

    # Basic validations
    if not file or file.filename == "":
        flash("Please select a student file.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not _allowed_file(file.filename):
        flash("Only CSV or Excel files are allowed for students.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if not department or not session_start_year or not session_end_year:
        flash("Department and session years are required for students.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    try:
        session_start_year = int(session_start_year)
        session_end_year = int(session_end_year)
    except ValueError:
        flash("Session years must be valid numbers.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower()

    # Read file with pandas
    try:
        if ext == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        print("Error reading student file:", e)
        flash("Could not read the student file. Check format.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    # Column handling (case-insensitive)
    lowered_cols = {c.lower().strip(): c for c in df.columns}

    # At minimum, require name + email
    required_cols = {"name", "email"}
    if not required_cols.issubset(set(lowered_cols.keys())):
        flash("Student file must have at least 'name' and 'email' columns.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    created_count = 0
    skipped_missing_required = 0
    skipped_duplicates = []

    # Normalise department for roll numbers
    dept_norm = department.upper().replace(" ", "")

    for _, row in df.iterrows():
        # ---------- BASIC FIELDS (REQUIRED) ----------
        name = str(row.get(lowered_cols["name"]) or "").strip()
        email = str(row.get(lowered_cols["email"]) or "").strip()

        # New fields (optional but recommended)
        dob_str = str(row.get(lowered_cols.get("dob", ""), "") or "").strip()
        aadhaar_number = str(row.get(lowered_cols.get("aadhaar_number", ""), "") or "").strip()
        marital_status = str(row.get(lowered_cols.get("marital_status", ""), "") or "").strip()
        pan_number = str(row.get(lowered_cols.get("pan_number", ""), "") or "").strip()
        contact_number = str(row.get(lowered_cols.get("contact_number", ""), "") or "").strip()
        abc_card = str(row.get(lowered_cols.get("abc_card", ""), "") or "").strip()
        father_name = str(row.get(lowered_cols.get("father_name", ""), "") or "").strip()
        mother_name = str(row.get(lowered_cols.get("mother_name", ""), "") or "").strip()
        father_contact = str(row.get(lowered_cols.get("father_contact", ""), "") or "").strip()
        mother_contact = str(row.get(lowered_cols.get("mother_contact", ""), "") or "").strip()
        address = str(row.get(lowered_cols.get("address", ""), "") or "").strip()

        # If any row missing basic required fields → skip
        if not name or not email:
            skipped_missing_required += 1
            continue

        # ---------- AGE CALCULATION (FROM DOB) ----------
        dob_date = None
        age = None
        if dob_str:
            try:
                dob_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
                age = calculate_age(dob_date)
            except Exception:
                # Invalid DOB format -> ignore age, but still accept student
                dob_date = None
                age = None

        # ---------- DUPLICATE CHECK (Aadhaar / PAN / Email / Contact) ----------
        unique_filters = []
        if aadhaar_number:
            unique_filters.append({"aadhaar_number": aadhaar_number})
        if pan_number:
            unique_filters.append({"pan_number": pan_number})
        if email:
            unique_filters.append({"email": email})
        if contact_number:
            unique_filters.append({"contact_number": contact_number})

        is_duplicate = False
        if unique_filters:
            existing = students_collection.find_one({"$or": unique_filters})
            if existing:
                is_duplicate = True

        if is_duplicate:
            skipped_duplicates.append({
                "name": name,
                "email": email,
                "reason": "Duplicate Aadhaar/PAN/Email/Contact"
            })
            continue

        # ---------- GENERATE REGISTRATION + ROLL ----------
        reg_no = generate_student_registration_number()
        roll_no = generate_student_roll_number(dept_norm, session_start_year)

        plain_password = f"Welcome@{reg_no}"
        password_hash = generate_password_hash(plain_password)

        # ---------- BUILD DOCUMENT ----------
        doc = {
            "registration_number": reg_no,
            "roll_number": roll_no,
            "name": name,
            "dob": dob_str or None,
            "age": age,
            "aadhaar_number": aadhaar_number or None,
            "marital_status": marital_status or None,
            "pan_number": pan_number or None,
            "contact_number": contact_number or None,
            "email": email,
            "abc_card": abc_card or None,
            "father_name": father_name or None,
            "mother_name": mother_name or None,
            "father_contact": father_contact or None,
            "mother_contact": mother_contact or None,
            "address": address or None,
            "department": dept_norm,
            "category": category or None,
            "label": label or None,
            "session_start_year": session_start_year,
            "session_end_year": session_end_year,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

        # ---------- SAVE + SEND EMAIL ----------
        students_collection.insert_one(doc)

        send_student_credentials_email(
            to_email=email,
            registration_number=reg_no,
            roll_number=roll_no,
            plain_password=plain_password,
            name=name,
        )

        created_count += 1

    # ---------- FLASH MESSAGES ----------
    if created_count > 0:
        flash(f"Successfully created {created_count} student accounts in MongoDB.", "success")
    if skipped_missing_required > 0:
        flash(f"{skipped_missing_required} rows were skipped due to missing required fields (name/email).", "error")
    if skipped_duplicates:
        flash(f"{len(skipped_duplicates)} rows were skipped due to duplicate Aadhaar/PAN/Email/Contact.", "error")

    return redirect(url_for("auth_bp.dict_dashboard"))

@auth_bp.route("/dict/students", methods=["GET"])
def dict_students():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    page = int(request.args.get("page", 1))
    per_page = 30
    skip = (page - 1) * per_page

    filters = []

    # Search filter
    if q:
        filters.append({
            "$or": [
                {"registration_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"department": {"$regex": q, "$options": "i"}},
            ]
        })

    # Date range filter on created_at
    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            # end of the day
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    total = students_collection.count_documents(query)

    students = list(
        students_collection.find(
            query,
            {
                "_id": 1,
                "registration_number": 1,
                "roll_number": 1,
                "name": 1,
                "email": 1,
                "department": 1,
                "session_start_year": 1,
                "session_end_year": 1,
            }
        )
        .sort("registration_number", 1)
        .skip(skip)
        .limit(per_page)
    )

    for s in students:
        s["_id"] = str(s["_id"])

    total_pages = (total + per_page - 1) // per_page

    # Dept-wise counts FOR FILTERED SET (respecting date + search)
    pipeline = []
    if query:
        pipeline.append({"$match": query})
    pipeline.extend([
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ])
    dept_counts = list(students_collection.aggregate(pipeline))

    return render_template(
        "dict_students.html",
        students=students,
        search_query=q,
        page=page,
        total_pages=total_pages,
        total=total,
        dept_counts=dept_counts,
        from_date=from_date_str,
        to_date=to_date_str,
    )



@auth_bp.route("/dict/students/edit/<student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    """
    View + update a single student's details.
    Only HSD / DICT employees can access this.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    try:
        obj_id = ObjectId(student_id)
    except Exception:
        flash("Invalid student ID.", "error")
        return redirect(url_for("auth_bp.dict_students"))

    if request.method == "GET":
        student = students_collection.find_one({"_id": obj_id})
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("auth_bp.dict_students"))

        # Convert _id to string for template
        student["_id"] = str(student["_id"])
        return render_template("dict_student_edit.html", student=student)

    # POST: update student
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    category = request.form.get("category", "").strip()
    label = request.form.get("label", "").strip()
    session_start_year = request.form.get("session_start_year", "").strip()
    session_end_year = request.form.get("session_end_year", "").strip()

    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("auth_bp.edit_student", student_id=student_id))

    update_doc = {
        "name": name,
        "email": email,
        "phone": phone or None,
        "department": department or None,
        "category": category or None,
        "label": label or None,
    }

    try:
        if session_start_year:
            update_doc["session_start_year"] = int(session_start_year)
        if session_end_year:
            update_doc["session_end_year"] = int(session_end_year)
    except ValueError:
        flash("Session years must be valid numbers.", "error")
        return redirect(url_for("auth_bp.edit_student", student_id=student_id))

    try:
        students_collection.update_one({"_id": obj_id}, {"$set": update_doc})
        flash("Student details updated successfully.", "success")
    except Exception as e:
        print("Error updating student:", e)
        flash("An error occurred while updating the student.", "error")

    return redirect(url_for("auth_bp.dict_students"))

@auth_bp.route("/dict/students/delete/<student_id>", methods=["POST"])
def delete_student(student_id):
    """
    Delete a student by MongoDB _id.
    Only HSD / DICT employees can perform this.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    students_collection = db_mongo["students"]

    try:
        result = students_collection.delete_one({"_id": ObjectId(student_id)})
        if result.deleted_count == 1:
            flash("Student deleted successfully.", "success")
        else:
            flash("Student not found or already deleted.", "error")
    except Exception as e:
        print("Error deleting student:", e)
        flash("An error occurred while deleting the student.", "error")

    return redirect(url_for("auth_bp.dict_students"))

@auth_bp.route("/dict/teachers", methods=["GET"])
def dict_teachers():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    page = int(request.args.get("page", 1))
    per_page = 30
    skip = (page - 1) * per_page

    filters = []

    if q:
        filters.append({
            "$or": [
                {"registration_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"department": {"$regex": q, "$options": "i"}},
            ]
        })

    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    total = teachers_collection.count_documents(query)

    teachers = list(
        teachers_collection.find(
            query,
            {
                "_id": 1,
                "registration_number": 1,
                "name": 1,
                "email": 1,
                "department": 1,
                "designation": 1,
                "session_start_year": 1,
                "session_end_year": 1,
            }
        )
        .sort("registration_number", 1)
        .skip(skip)
        .limit(per_page)
    )

    for t in teachers:
        t["_id"] = str(t["_id"])

    total_pages = (total + per_page - 1) // per_page

    # Department-wise counts (filtered)
    pipeline = []
    if query:
        pipeline.append({"$match": query})
    pipeline.extend([
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ])
    dept_counts = list(teachers_collection.aggregate(pipeline))

    return render_template(
        "dict_teachers.html",
        teachers=teachers,
        search_query=q,
        page=page,
        total_pages=total_pages,
        total=total,
        dept_counts=dept_counts,
        from_date=from_date_str,
        to_date=to_date_str,
    )


@auth_bp.route("/dict/teachers/edit/<teacher_id>", methods=["GET", "POST"])
def edit_teacher(teacher_id):
    """
    View + update a single teacher's details.
    Only HSD / DICT employees can access this.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    try:
        obj_id = ObjectId(teacher_id)
    except Exception:
        flash("Invalid teacher ID.", "error")
        return redirect(url_for("auth_bp.dict_teachers"))

    if request.method == "GET":
        teacher = teachers_collection.find_one({"_id": obj_id})
        if not teacher:
            flash("Teacher not found.", "error")
            return redirect(url_for("auth_bp.dict_teachers"))

        teacher["_id"] = str(teacher["_id"])
        return render_template("dict_teacher_edit.html", teacher=teacher)

    # POST: update teacher
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()
    session_start_year = request.form.get("session_start_year", "").strip()
    session_end_year = request.form.get("session_end_year", "").strip()

    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("auth_bp.edit_teacher", teacher_id=teacher_id))

    update_doc = {
        "name": name,
        "email": email,
        "phone": phone or None,
        "department": department or None,
        "designation": designation or None,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        if session_start_year:
            update_doc["session_start_year"] = int(session_start_year)
        if session_end_year:
            update_doc["session_end_year"] = int(session_end_year)
    except ValueError:
        flash("Session years must be valid numbers.", "error")
        return redirect(url_for("auth_bp.edit_teacher", teacher_id=teacher_id))

    try:
        teachers_collection.update_one({"_id": obj_id}, {"$set": update_doc})
        flash("Teacher details updated successfully.", "success")
    except Exception as e:
        print("Error updating teacher:", e)
        flash("An error occurred while updating the teacher.", "error")

    return redirect(url_for("auth_bp.dict_teachers"))

@auth_bp.route("/dict/teachers/delete/<teacher_id>", methods=["POST"])
def delete_teacher(teacher_id):
    """
    Delete a teacher by MongoDB _id.
    Only HSD / DICT employees can perform this.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    teachers_collection = db_mongo["teachers"]

    try:
        result = teachers_collection.delete_one({"_id": ObjectId(teacher_id)})
        if result.deleted_count == 1:
            flash("Teacher deleted successfully.", "success")
        else:
            flash("Teacher not found or already deleted.", "error")
    except Exception as e:
        print("Error deleting teacher:", e)
        flash("An error occurred while deleting the teacher.", "error")

    return redirect(url_for("auth_bp.dict_teachers"))

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
            "created_at": datetime.now(timezone.utc),
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

@auth_bp.route("/dict/staff", methods=["GET"])
def dict_staff():
    """
    Manage non-teaching staff with search, pagination, role-wise counts and date filter.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    page = int(request.args.get("page", 1))
    per_page = 30
    skip = (page - 1) * per_page

    filters = []

    if q:
        filters.append({
            "$or": [
                {"employee_number": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"role": {"$regex": q, "$options": "i"}},
            ]
        })

    date_range = {}
    if from_date_str:
        try:
            date_range["$gte"] = datetime.strptime(from_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date_str:
        try:
            dt = datetime.strptime(to_date_str, "%Y-%m-%d")
            date_range["$lte"] = dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    if date_range:
        filters.append({"created_at": date_range})

    if filters:
        query = {"$and": filters}
    else:
        query = {}

    total = staff_collection.count_documents(query)

    staff_list = list(
        staff_collection.find(
            query,
            {
                "_id": 1,
                "employee_number": 1,
                "name": 1,
                "email": 1,
                "contact_number": 1,
                "role": 1,
                "years_of_experience": 1,
                "date_of_joining": 1,
            }
        )
        .sort("employee_number", 1)
        .skip(skip)
        .limit(per_page)
    )

    for s in staff_list:
        s["_id"] = str(s["_id"])

    total_pages = (total + per_page - 1) // per_page

    # Role-wise staff counts (filtered)
    pipeline = []
    if query:
        pipeline.append({"$match": query})
    pipeline.extend([
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ])
    role_counts = list(staff_collection.aggregate(pipeline))

    roles = ["Library", "Canteen", "Examination", "Accounts", "Information"]

    return render_template(
        "dict_staff.html",
        staff_list=staff_list,
        search_query=q,
        page=page,
        total_pages=total_pages,
        total=total,
        role_counts=role_counts,
        roles=roles,
        from_date=from_date_str,
        to_date=to_date_str,
    )



@auth_bp.route("/dict/staff/add", methods=["GET", "POST"])
def add_staff():
    """
    Add a single non-teaching staff employee (Library, Canteen, etc.).
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    roles = ["Library", "Canteen", "Examination", "Accounts", "Information"]

    if request.method == "GET":
        return render_template("dict_staff_add.html", roles=roles)

    # POST: process form
    name = request.form.get("name", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    email = request.form.get("email", "").strip()
    dob = request.form.get("dob", "").strip()
    years_of_experience = request.form.get("years_of_experience", "").strip()
    role = request.form.get("role", "").strip()
    date_of_joining = request.form.get("date_of_joining", "").strip()
    aadhaar_number = request.form.get("aadhaar_number", "").strip()
    pan_number = request.form.get("pan_number", "").strip()

    if not name or not email or not role:
        flash("Name, email, and role are required.", "error")
        return redirect(url_for("auth_bp.add_staff"))

    # Convert years_of_experience
    exp_years_int = 0
    if years_of_experience:
        try:
            exp_years_int = int(years_of_experience)
        except ValueError:
            flash("Years of experience must be a number.", "error")
            return redirect(url_for("auth_bp.add_staff"))

    # Aadhaar/PAN could reuse validation if you want; for now keep simple or call helpers if needed

    employee_number = generate_staff_employee_number()
    plain_password = f"Welcome@{employee_number}EMP"
    password_hash = generate_password_hash(plain_password)

    doc = {
        "employee_number": employee_number,
        "name": name,
        "contact_number": contact_number or None,
        "email": email,
        "dob": dob or None,  # store as string "YYYY-MM-DD" for now
        "years_of_experience": exp_years_int,
        "role": role,
        "date_of_joining": date_of_joining or None,
        "aadhaar_number": aadhaar_number or None,
        "pan_number": pan_number or None,
        "password_hash": password_hash,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }

    staff_collection.insert_one(doc)

    send_staff_credentials_email(
        to_email=email,
        employee_number=employee_number,
        plain_password=plain_password,
        name=name,
        role=role,
    )

    flash(f"Employee {employee_number} created and credentials emailed.", "success")
    return redirect(url_for("auth_bp.dict_staff"))

@auth_bp.route("/dict/staff/upload", methods=["POST"])
def upload_staff():
    """
    Bulk upload non-teaching staff from CSV/Excel.
    Expected columns (case-insensitive):
      name, email, contact_number, dob, years_of_experience,
      role, date_of_joining, aadhaar_number, pan_number
    Only name, email, role are strictly required.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    file = request.files.get("staff_file")
    if not file or file.filename == "":
        flash("Please select a staff file.", "error")
        return redirect(url_for("auth_bp.dict_staff"))

    if not _allowed_file(file.filename):
        flash("Only CSV or Excel files are allowed for staff upload.", "error")
        return redirect(url_for("auth_bp.dict_staff"))

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        print("Error reading staff file:", e)
        flash("Could not read the staff file. Check format.", "error")
        return redirect(url_for("auth_bp.dict_staff"))

    lowered_cols = {c.lower(): c for c in df.columns}

    required_cols = {"name", "email", "role"}
    if not required_cols.issubset(set(lowered_cols.keys())):
        flash("Staff file must have at least 'name', 'email', and 'role' columns.", "error")
        return redirect(url_for("auth_bp.dict_staff"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    created_count = 0

    for _, row in df.iterrows():
        name = str(row.get(lowered_cols["name"]) or "").strip()
        email = str(row.get(lowered_cols["email"]) or "").strip()
        role = str(row.get(lowered_cols["role"]) or "").strip()

        if not name or not email or not role:
            continue

        contact_number = str(row.get(lowered_cols.get("contact_number", ""), "") or "").strip()
        dob = str(row.get(lowered_cols.get("dob", ""), "") or "").strip()
        doj = str(row.get(lowered_cols.get("date_of_joining", ""), "") or "").strip()
        aadhaar = str(row.get(lowered_cols.get("aadhaar_number", ""), "") or "").strip()
        pan = str(row.get(lowered_cols.get("pan_number", ""), "") or "").strip()
        exp_raw = row.get(lowered_cols.get("years_of_experience", ""), "")

        exp_years = 0
        try:
            if str(exp_raw).strip() != "":
                exp_years = int(exp_raw)
        except Exception:
            exp_years = 0

        employee_number = generate_staff_employee_number()
        plain_password = f"Welcome@{employee_number}"
        password_hash = generate_password_hash(plain_password)

        doc = {
            "employee_number": employee_number,
            "name": name,
            "contact_number": contact_number or None,
            "email": email,
            "dob": dob or None,
            "years_of_experience": exp_years,
            "role": role,
            "date_of_joining": doj or None,
            "aadhaar_number": aadhaar or None,
            "pan_number": pan or None,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

        staff_collection.insert_one(doc)

        send_staff_credentials_email(
            to_email=email,
            employee_number=employee_number,
            plain_password=plain_password,
            name=name,
            role=role,
        )

        created_count += 1

    flash(f"Successfully created {created_count} staff employee accounts.", "success")
    return redirect(url_for("auth_bp.dict_staff"))

@auth_bp.route("/dict/staff/edit/<staff_id>", methods=["GET", "POST"])
def edit_staff(staff_id):
    """
    View + update a single staff employee.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    try:
        obj_id = ObjectId(staff_id)
    except Exception:
        flash("Invalid staff ID.", "error")
        return redirect(url_for("auth_bp.dict_staff"))

    roles = ["Library", "Canteen", "Examination", "Accounts", "Information"]

    if request.method == "GET":
        staff = staff_collection.find_one({"_id": obj_id})
        if not staff:
            flash("Staff employee not found.", "error")
            return redirect(url_for("auth_bp.dict_staff"))

        staff["_id"] = str(staff["_id"])
        return render_template("dict_staff_edit.html", staff=staff, roles=roles)

    # POST: update
    name = request.form.get("name", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    email = request.form.get("email", "").strip()
    dob = request.form.get("dob", "").strip()
    years_of_experience = request.form.get("years_of_experience", "").strip()
    role = request.form.get("role", "").strip()
    date_of_joining = request.form.get("date_of_joining", "").strip()
    aadhaar_number = request.form.get("aadhaar_number", "").strip()
    pan_number = request.form.get("pan_number", "").strip()

    if not name or not email or not role:
        flash("Name, email, and role are required.", "error")
        return redirect(url_for("auth_bp.edit_staff", staff_id=staff_id))

    exp_years_int = 0
    if years_of_experience:
        try:
            exp_years_int = int(years_of_experience)
        except ValueError:
            flash("Years of experience must be a number.", "error")
            return redirect(url_for("auth_bp.edit_staff", staff_id=staff_id))

    update_doc = {
        "name": name,
        "contact_number": contact_number or None,
        "email": email,
        "dob": dob or None,
        "years_of_experience": exp_years_int,
        "role": role,
        "date_of_joining": date_of_joining or None,
        "aadhaar_number": aadhaar_number or None,
        "pan_number": pan_number or None,
    }

    try:
        staff_collection.update_one({"_id": obj_id}, {"$set": update_doc})
        flash("Staff employee details updated successfully.", "success")
    except Exception as e:
        print("Error updating staff:", e)
        flash("An error occurred while updating the staff employee.", "error")

    return redirect(url_for("auth_bp.dict_staff"))

@auth_bp.route("/dict/staff/delete/<staff_id>", methods=["POST"])
def delete_staff(staff_id):
    """
    Delete a staff employee by MongoDB _id.
    """
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    staff_collection = db_mongo["staff"]

    try:
        result = staff_collection.delete_one({"_id": ObjectId(staff_id)})
        if result.deleted_count == 1:
            flash("Staff employee deleted successfully.", "success")
        else:
            flash("Staff employee not found or already deleted.", "error")
    except Exception as e:
        print("Error deleting staff:", e)
        flash("An error occurred while deleting the staff employee.", "error")

    return redirect(url_for("auth_bp.dict_staff"))

@auth_bp.route("/dict/contact-requests")
def dict_contact_requests():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    db_mongo = get_mongo_db()
    contact_collection = db_mongo["contact_requests"]

    page = int(request.args.get("page", 1))
    per_page = 30
    skip = (page - 1) * per_page

    total = contact_collection.count_documents({})
    requests_list = list(
        contact_collection
        .find({})
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    for r in requests_list:
        r["_id"] = str(r["_id"])

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "dict_contact_requests.html",
        requests_list=requests_list,
        page=page,
        total_pages=total_pages,
        total=total,
    )

@auth_bp.route("/dict/profile", methods=["GET", "POST"])
def dict_profile():
    if session.get("user_role") != "hsd":
        return redirect(url_for("auth_bp.login"))

    emp_id = session.get("user_id")
    emp = Employee.query.get(emp_id)
    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for("auth_bp.dict_dashboard"))

    if request.method == "GET":
        return render_template("dict_profile.html", emp=emp)

    # POST: update basic fields + upload photo
    name = request.form.get("name", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    address = request.form.get("address", "").strip()

    if name:
        emp.name = name
    if contact_number:
        emp.contact_number = contact_number
    if address:
        emp.address = address

    file = request.files.get("profile_photo")
    if file and file.filename:
        filename = secure_filename(file.filename)
        upload_folder = current_app.config.get("PROFILE_UPLOAD_FOLDER", "static/uploads/profiles")
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        # store relative path
        emp.profile_photo = filepath.replace("\\", "/")

    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("auth_bp.dict_profile"))
