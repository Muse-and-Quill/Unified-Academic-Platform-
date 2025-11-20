# seed_employees.py
from app import create_app
from utils.helpers import create_employee_from_data


def prompt_employee() -> dict:
    print("=== Add DICT Employee ===")
    name = input("Full Name: ").strip()
    email = input("Email (Gmail preferred): ").strip()
    contact_number = input("Contact Number: ").strip()
    dob = input("Date of Birth (YYYY-MM-DD): ").strip()
    department = input("Department [default DICT]: ").strip() or "DICT"
    aadhaar_number = input("Aadhaar (12 digits): ").strip()
    pan_number = input("PAN: ").strip()
    profile_photo = input("Profile Photo path/URL (optional, press Enter to skip): ").strip()
    date_of_joining = input("Date of Joining (YYYY-MM-DD): ").strip()
    address = input("Address: ").strip()

    data = {
        "name": name,
        "email": email,
        "contact_number": contact_number,
        "dob": dob,
        "department": department,
        "aadhaar_number": aadhaar_number,
        "pan_number": pan_number,
        "profile_photo": profile_photo if profile_photo else None,
        "date_of_joining": date_of_joining,
        "address": address,
    }
    return data


if __name__ == "__main__":
    print("▶ Starting seed_employees.py...")

    app = create_app()
    print("✅ Flask app created.")

    with app.app_context():
        print("✅ App context active. Ready to add employees.\n")

        while True:
            try:
                data = prompt_employee()
                emp = create_employee_from_data(data)
                print(f"\n✅ Employee created: {emp.employee_id} ({emp.name})")
                print("   Email was attempted to:", emp.email)
            except Exception as e:
                print("❌ Error while creating employee:", e)

            more = input("\nAdd another employee? (y/n): ").strip().lower()
            if more != "y":
                print("👋 Exiting seeding script.")
                break
