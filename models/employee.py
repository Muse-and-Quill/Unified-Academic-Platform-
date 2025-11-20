from datetime import datetime
from . import db

class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)

    # Auto-generated
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Seeded by you
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact_number = db.Column(db.String(15), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    age = db.Column(db.Integer, nullable=False)

    department = db.Column(db.String(50), nullable=False, default="DICT")
    aadhaar_number = db.Column(db.String(12), unique=True, nullable=False)
    pan_number = db.Column(db.String(10), unique=True, nullable=False)

    profile_photo = db.Column(db.String(255), nullable=True)  # can be blank or null
    date_of_joining = db.Column(db.Date, nullable=False)
    address = db.Column(db.Text, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Employee {self.employee_id} - {self.name}>"
