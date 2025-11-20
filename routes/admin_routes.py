from flask import Blueprint, request, jsonify
from models import db
from models.employee import Employee
from utils.helpers import (
    calculate_age,
    validate_aadhaar,
    validate_pan,
)

admin_bp = Blueprint("admin_bp", __name__)

# ---------- LIST EMPLOYEES ----------
@admin_bp.route("/employees", methods=["GET"])
def list_employees():
    department = request.args.get("department")
    query = Employee.query
    if department:
        query = query.filter_by(department=department)

    employees = query.all()
    result = []
    for emp in employees:
        result.append({
            "employee_id": emp.employee_id,
            "name": emp.name,
            "email": emp.email,
            "contact_number": emp.contact_number,
            "dob": emp.dob.isoformat(),
            "age": emp.age,
            "department": emp.department,
            "aadhaar_number": emp.aadhaar_number,
            "pan_number": emp.pan_number,
            "profile_photo": emp.profile_photo,
            "date_of_joining": emp.date_of_joining.isoformat(),
            "address": emp.address,
            "is_active": emp.is_active,
        })
    return jsonify({"success": True, "employees": result})

# ---------- GET SINGLE EMPLOYEE ----------
@admin_bp.route("/employees/<employee_id>", methods=["GET"])
def get_employee(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({"success": False, "message": "Employee not found"}), 404

    return jsonify({
        "success": True,
        "employee": {
            "employee_id": emp.employee_id,
            "name": emp.name,
            "email": emp.email,
            "contact_number": emp.contact_number,
            "dob": emp.dob.isoformat(),
            "age": emp.age,
            "department": emp.department,
            "aadhaar_number": emp.aadhaar_number,
            "pan_number": emp.pan_number,
            "profile_photo": emp.profile_photo,
            "date_of_joining": emp.date_of_joining.isoformat(),
            "address": emp.address,
            "is_active": emp.is_active,
        }
    })

# ---------- UPDATE EMPLOYEE (ADMIN ONLY) ----------
@admin_bp.route("/employees/<employee_id>", methods=["PUT"])
def update_employee(employee_id):
    emp = Employee.query.filter_by(employee_id=employee_id).first()
    if not emp:
        return jsonify({"success": False, "message": "Employee not found"}), 404

    data = request.get_json() or {}

    if "name" in data:
        emp.name = data["name"].strip()

    if "email" in data:
        emp.email = data["email"].strip()

    if "contact_number" in data:
        emp.contact_number = data["contact_number"].strip()

    if "dob" in data:
        from datetime import datetime
        new_dob = datetime.strptime(data["dob"], "%Y-%m-%d").date()
        emp.dob = new_dob
        emp.age = calculate_age(new_dob)

    if "department" in data:
        emp.department = data["department"].strip()

    if "profile_photo" in data:
        emp.profile_photo = data["profile_photo"] or None

    if "date_of_joining" in data:
        from datetime import datetime
        emp.date_of_joining = datetime.strptime(
            data["date_of_joining"], "%Y-%m-%d"
        ).date()

    if "address" in data:
        emp.address = data["address"].strip()

    if "is_active" in data:
        emp.is_active = bool(data["is_active"])

    if "aadhaar_number" in data:
        aadhaar = data["aadhaar_number"].strip()
        if not validate_aadhaar(aadhaar):
            return jsonify({"success": False, "message": "Invalid Aadhaar."}), 400
        emp.aadhaar_number = aadhaar

    if "pan_number" in data:
        pan = data["pan_number"].strip().upper()
        name_parts = emp.name.strip().split()
        surname_letter = name_parts[-1][0] if name_parts else None
        if not validate_pan(pan, surname_letter):
            return jsonify({"success": False, "message": "Invalid PAN."}), 400
        emp.pan_number = pan

    db.session.commit()
    return jsonify({"success": True, "message": "Employee updated successfully."})
