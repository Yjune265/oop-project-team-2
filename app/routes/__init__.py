from .user_routes import user_bp
from .admin_routes import admin_bp
from .survey_routes import survey_bp
from .supplement_routes import supplement_bp


def register_blueprints(app):
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(survey_bp, url_prefix="/api/survey")
    app.register_blueprint(supplement_bp, url_prefix="/api/supplement")
