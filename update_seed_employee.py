# update_seed_employee.py
"""
CLI tool to update a DICT Employee (seeded employee) from terminal.
- Allows updating: name, email, contact, department, address
- Optional password change
- Sends an email notification after successful update
"""

from getpass import getpass

from app import app
from models import db
from models.employee import Employee
from utils.email_service import send_account_updated_email


def main():
    with app.app_context():
        emp_id = input("Enter Employee ID to update (e.g., DICT001): ").strip()
        if not emp_id:
            print("Employee ID is required.")
            return

        emp = Employee.query.filter_by(employee_id=emp_id).first()

        if not emp:
            print(f"Employee with ID {emp_id} not found.")
            return

        print("\n--- Current Employee Details ---")
        print(f"Employee ID : {emp.employee_id}")
        print(f"Name        : {emp.name}")
        print(f"Email       : {emp.email}")
        print(f"Contact     : {emp.contact_number or ''}")
        print(f"Department  : {emp.department or ''}")
        print(f"Address     : {emp.address or ''}")
        print(f"Active      : {emp.is_active}")
        print("--------------------------------\n")

        print("Leave any field blank to keep the existing value.\n")

        new_name = input(f"New Name [{emp.name}]: ").strip()
        new_email = input(f"New Email [{emp.email}]: ").strip()
        new_contact = input(f"New Contact Number [{emp.contact_number or ''}]: ").strip()
        new_dept = input(f"New Department [{emp.department or ''}]: ").strip()
        new_address = input(f"New Address [{emp.address or ''}]: ").strip()

        # Password change
        from werkzeug.security import generate_password_hash

        change_password = input("Change password? (y/N): ").strip().lower()
        if change_password == "y":
            new_pass = getpass("Enter new password: ")
            confirm_pass = getpass("Confirm new password: ")
            if new_pass != confirm_pass:
                print("❌ Passwords do not match. Password will not be changed.")
            elif len(new_pass) < 8:
                print("❌ Password too short (min 8 chars). Password will not be changed.")
            else:
                emp.password_hash = generate_password_hash(new_pass)
                print("✅ Password updated.")

        # Apply changes ONLY if non-empty
        if new_name:
            emp.name = new_name
        if new_email:
            emp.email = new_email
        if new_contact:
            emp.contact_number = new_contact
        if new_dept:
            emp.department = new_dept
        if new_address:
            emp.address = new_address

        db.session.commit()
        print("\n✅ Employee updated successfully in database.")

        # Send email notification
        try:
            ok = send_account_updated_email(emp.email, emp.name, emp.employee_id)
            if ok:
                print("📧 Account update email sent.")
            else:
                print("⚠ Failed to send account update email.")
        except Exception as e:
            print("⚠ Error sending account update email:", e)


if __name__ == "__main__":
    main()