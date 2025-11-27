from flask import Flask
from config import Config
from app.routes import register_blueprints


def create_app():
    app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
    app.config.from_object(Config)
    register_blueprints(app)


    @app.route("/")
    def home():
        return "NutriGuide Backend Running"


    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)