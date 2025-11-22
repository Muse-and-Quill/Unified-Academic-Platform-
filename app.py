from flask import Flask, render_template, g, request
from config import Config
from models import db
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from flask import Flask, render_template, g, request, redirect, url_for, flash
from utils.mongo_client import get_mongo_db
from dotenv import load_dotenv
from utils.mongo_client import get_mongo_client
from datetime import datetime

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Initialize SQLAlchemy (for Employee table)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ---------- REGISTER BLUEPRINTS ----------
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp)   # /login, /logout, /dict/dashboard, etc.

    # ---------- BASIC PAGES ----------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")


    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "GET":
            return render_template("contact-us.html")

        # POST: save contact request
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill all required fields.", "error")
            return render_template("contact-us.html")

        db_mongo = get_mongo_db()
        contact_collection = db_mongo["contact_requests"]

        contact_collection.insert_one({
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "status": "new",
            "created_at": datetime.utcnow()
        })

        flash("Your message has been sent successfully.", "success")
        return redirect(url_for("contact"))
    
    # ---------- NO-CACHE HEADERS (IMPORTANT) ----------
    @app.after_request
    def add_no_cache_headers(response):
        """
        Prevent browsers from caching pages, so after logout
        the user cannot see the old dashboard using back/forward.
        """
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # ---------- TEARDOWN: MONGODB ----------
    @app.teardown_appcontext
    def teardown_mongo(exception):
        mongo_client = g.pop("mongo_client", None)
        if mongo_client is not None:
            mongo_client.close()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
