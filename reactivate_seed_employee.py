# reactivate_seed_employee.py
"""
CLI tool to reactivate a previously inactive DICT Employee.
- Sets is_active = True
- Sends reactivation email notification
"""

from app import app
from models import db
from models.employee import Employee
from utils.email_service import send_account_reactivated_email


def main():
    with app.app_context():
        emp_id = input("Enter Employee ID to reactivate (e.g., DICT004): ").strip()
        if not emp_id:
            print("Employee ID is required.")
            return

        emp = Employee.query.filter_by(employee_id=emp_id).first()

        if not emp:
            print(f"Employee with ID {emp_id} not found.")
            return

        print("\n--- Employee Details ---")
        print(f"Employee ID : {emp.employee_id}")
        print(f"Name        : {emp.name}")
        print(f"Email       : {emp.email}")
        print(f"Active      : {emp.is_active}")
        print("-------------------------\n")

        if emp.is_active:
            print(f"Employee {emp.employee_id} is already ACTIVE.")
            return

        confirm = input(f"Reactivate {emp.employee_id}? (y/N): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

        emp.is_active = True
        db.session.commit()
        print(f"✅ Employee {emp.employee_id} has been reactivated.")

        # Send reactivation email
        try:
            ok = send_account_reactivated_email(emp.email, emp.name, emp.employee_id)
            if ok:
                print("📧 Reactivation email sent.")
            else:
                print("⚠ Failed to send reactivation email.")
        except Exception as e:
            print("⚠ Error sending reactivation email:", e)


if __name__ == "__main__":
    main()