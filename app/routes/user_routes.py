# app/routes/user_routes.py
from flask import Blueprint, request, jsonify
# ✅ 제 로직 파일 위치로 수정 (app/services/app_logic.py)
from app.services.app_logic import UserProfileManager 

user_bp = Blueprint("user_bp", __name__)

@user_bp.route("/profile", methods=["POST"])
def save_profile():
    try:
        data = request.json
        manager = UserProfileManager()
        
        # ✅ 주의: app_logic.py에 save_user_profile 메서드가 있어야 함.
        # 만약 save_survey_data 하나로 다 처리한다면 그걸 호출해야 함.
        # 여기서는 프로필만 따로 저장하는 기능이라고 가정하고 연결.
        result = manager.save_user_profile(data) 
        
        return jsonify({"status": "success", "user_id": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500