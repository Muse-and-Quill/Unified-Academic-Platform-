# delete_seed_employee.py
"""
CLI tool to deactivate or permanently delete a DICT Employee.
- Default behavior: mark as inactive (soft delete)
- Optional hard delete (requires 'DELETE' confirmation)
- Sends appropriate email notifications
"""

from app import app
from models import db
from models.employee import Employee
from utils.email_service import send_account_deactivated_email


def main():
    with app.app_context():
        emp_id = input("Enter Employee ID to deactivate/delete (e.g., DICT001): ").strip()
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

        choice = input("Set as INACTIVE (soft delete)? (Y/n): ").strip().lower()

        if choice in ("", "y", "yes"):
            if not emp.is_active:
                print(f"Employee {emp.employee_id} is already inactive.")
            else:
                emp.is_active = False
                db.session.commit()
                print(f"✅ Employee {emp.employee_id} marked as inactive.")

                # Send deactivation email
                try:
                    ok = send_account_deactivated_email(emp.email, emp.name, emp.employee_id)
                    if ok:
                        print("📧 Deactivation email sent.")
                    else:
                        print("⚠ Failed to send deactivation email.")
                except Exception as e:
                    print("⚠ Error sending deactivation email:", e)

        else:
            confirm = input(
                f"⚠ HARD DELETE: Are you sure you want to permanently DELETE {emp.employee_id}? "
                "This cannot be undone. Type 'DELETE' to confirm: "
            ).strip()

            if confirm == "DELETE":
                # Optional: inform them account is terminated
                try:
                    ok = send_account_deactivated_email(emp.email, emp.name, emp.employee_id)
                    if ok:
                        print("📧 Termination email sent before deletion.")
                    else:
                        print("⚠ Failed to send termination email.")
                except Exception as e:
                    print("⚠ Error sending termination email:", e)

                db.session.delete(emp)
                db.session.commit()
                print(f"❌ Employee {emp.employee_id} deleted permanently.")
            else:
                print("Operation cancelled.")


if __name__ == "__main__":
    main()