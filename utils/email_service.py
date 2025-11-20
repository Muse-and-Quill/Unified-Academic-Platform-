import smtplib
from email.mime.text import MIMEText
from flask import current_app


def send_credentials_email(to_email: str, employee_id: str, plain_password: str, name: str) -> bool:
    """
    Sends initial credentials email for DICT / HSD employees.
    """
    subject = "Your UAP DICT Employee Credentials"
    body = f"""
Dear {name},

Your Unified Academic Platform (UAP) DICT employee account has been created.

Employee ID : {employee_id}
Email       : {to_email}
Password    : {plain_password}

Please log in and change your password after your first login.

Regards,
Unified Academic Platform (UAP)
"""
    return _send_email(subject, body, to_email)


def send_reset_password_email(to_email: str, reset_url: str, name: str) -> bool:
    """
    Sends password reset link email for employees.
    """
    subject = "UAP DICT Password Reset Request"
    body = f"""
Dear {name},

We received a request to reset your Unified Academic Platform (UAP) DICT account password.

You can set a new password by clicking the link below (this link will expire in 1 hour):

{reset_url}

If you did not request this, you can safely ignore this email.

Regards,
Unified Academic Platform (UAP)
"""
    return _send_email(subject, body, to_email)


def send_student_credentials_email(
    to_email: str,
    registration_number: str,
    roll_number: str,
    plain_password: str,
    name: str
) -> bool:
    """
    Sends initial credentials email to a student.
    """
    subject = "Your Unified Academic Platform (UAP) Student Credentials"
    body = f"""
Dear {name},

Your Unified Academic Platform (UAP) student account has been created.

Registration Number : {registration_number}
Roll Number         : {roll_number}
Email               : {to_email}
Password            : {plain_password}

You can now log in to the UAP Student Dashboard using these credentials.
Please change your password after your first login.

Regards,
Unified Academic Platform (UAP)
"""
    return _send_email(subject, body, to_email)


def send_teacher_credentials_email(
    to_email: str,
    registration_number: str,
    plain_password: str,
    name: str,
    department: str
) -> bool:
    """
    Sends initial credentials email to a teacher.
    """
    subject = "Your Unified Academic Platform (UAP) Teacher Credentials"
    body = f"""
Dear {name},

Your Unified Academic Platform (UAP) teacher account has been created.

Registration Number : {registration_number}
Department          : {department}
Email               : {to_email}
Password            : {plain_password}

You can now log in to the UAP Teacher Dashboard using these credentials.
Please change your password after your first login.

Regards,
Unified Academic Platform (UAP)
"""
    return _send_email(subject, body, to_email)


def _send_email(subject: str, body: str, to_email: str) -> bool:
    """
    Low-level email sender using SMTP + Flask config.
    """
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = to_email

    mail_server = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port = current_app.config.get("MAIL_PORT", 587)
    use_tls = current_app.config.get("MAIL_USE_TLS", False)
    use_ssl = current_app.config.get("MAIL_USE_SSL", False)
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(mail_server, mail_port)
        else:
            server = smtplib.SMTP(mail_server, mail_port)

        server.ehlo()

        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()

        if username and password:
            server.login(username, password)

        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:
        print("Error sending email:", e)
        return False
