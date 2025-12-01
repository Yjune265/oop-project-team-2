# app/routes/survey_routes.py
from flask import Blueprint, request, jsonify
from app.services.app_logic import UserProfileManager, RecommendationEngine

survey_bp = Blueprint("survey_bp", __name__)

@survey_bp.route("/submit", methods=["POST"])
def submit_survey():
    try:
        data = request.json
        
        # 1. 저장 로직 (제 것 사용)
        profile_mgr = UserProfileManager()
        user_id = profile_mgr.save_survey_data(data)
        
        # 2. 추천 로직 (제 것 사용)
        rec_engine = RecommendationEngine(user_id)
        
        # ✅ 함수 이름 수정: engine.recommend() -> engine.run_recommendation()
        recommendations = rec_engine.run_recommendation()
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "results": recommendations
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500