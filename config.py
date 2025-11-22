import os

class Config:
    PROFILE_UPLOAD_FOLDER = "static/uploads/profiles"
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
    # ========================
    # FLASK / APP SETTINGS
    # ========================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET", "dev-jwt-secret")

    # ========================
    # DATABASE (SQL FOR EMPLOYEES)
    # ========================
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///uap.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ========================
    # MONGODB (FOR STUDENTS & TEACHERS)
    # ========================
    MONGODB_URI = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://infounifiedacademics_db_user:sachinpokemon@uap.vpd12hn.mongodb.net/?appName=UAP"
    )
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "uap_db")

    # ========================
    # EMAIL SETTINGS
    # ========================
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False") == "True"

    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "info.unifiedacademics@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "ghys gubd xvkn oyfo")
    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        os.getenv("MAIL_USERNAME", "info.unifiedacademics@gmail.com")
    )
