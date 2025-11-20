from flask import Flask, render_template, g
from config import Config
from models import db
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp

from dotenv import load_dotenv
from utils.mongo_client import get_mongo_client

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

    @app.route("/contact")
    def contact():
        return render_template("contact-us.html")

    # ---------- TEARDOWN: MONGODB ----------
    @app.teardown_appcontext
    def teardown_mongo(exception):
        mongo_client = g.pop("mongo_client", None)
        if mongo_client is not None:
            mongo_client.close()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
