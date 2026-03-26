"""
Perplex - Contract Intelligence Platform
Main Flask Application Entry Point
"""

from flask import Flask
from flask_cors import CORS
import os

from backend.routes.contract_routes import contract_bp
from backend.routes.query_routes import query_bp
from backend.routes.health_routes import health_bp

def create_app():
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available, use system env vars
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static"
    )

    # Configuration
    app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "data", "uploads")
    app.config["INDEX_FOLDER"] = os.path.join(os.getcwd(), "data", "indexes")
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB max upload
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "perplex-dev-secret")

    # Ensure required directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["INDEX_FOLDER"], exist_ok=True)

    # CORS
    CORS(app)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(contract_bp, url_prefix="/api/contracts")
    app.register_blueprint(query_bp, url_prefix="/api/query")

    # Serve frontend
    from flask import render_template
    @app.route("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
