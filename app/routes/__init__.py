# app/routes/__init__.py
from flask import Flask
# 1. interaction_routes 임포트 제거
# from .interaction_routes import interaction_bp  <-- 삭제 또는 주석 처리

from .user_routes import user_bp
from .admin_routes import admin_bp
from .survey_routes import survey_bp
from .supplement_routes import supplement_bp
# recommend_bp는 survey_bp와 역할이 겹칠 수 있으나, 팀원이 만들어뒀다면 유지하되 내용만 맞추면 됩니다.

def register_blueprints(app: Flask):
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(survey_bp, url_prefix="/api/survey")
    app.register_blueprint(supplement_bp, url_prefix="/api/supplement")
    
    # app.register_blueprint(interaction_bp, url_prefix="/api/interaction") <-- 삭제 또는 주석 처리