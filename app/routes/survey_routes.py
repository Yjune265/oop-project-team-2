from flask import Blueprint, request, jsonify
from app.services.app_logic import UserProfileManager, RecommendationEngine


survey_bp = Blueprint("survey_bp", __name__)


@survey_bp.route("/submit", methods=["POST"])
def submit_survey():
    data = request.json
    manager = UserProfileManager()
    user_id = manager.save_survey_data(data)
    engine = RecommendationEngine(user_id)
    rec = engine.recommend()
    return jsonify(rec)