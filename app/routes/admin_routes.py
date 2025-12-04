# app/routes/admin_routes.py
from flask import Blueprint, jsonify, request
# ✅ 저의 관리자 로직 파일 위치로 수정
from app.services.admin_logic import AdminManager

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/users", methods=["GET"])
def list_users():
    try:
        manager = AdminManager()
        
        # ✅ 제가 만든 함수 이름으로 호출 (예: 최근 가입자 50명 조회)
        # 만약 list_all_users가 없다면 get_recent_users로 연결
        users = manager.get_recent_users(limit=50) 
        
        return jsonify({"status": "success", "count": len(users), "users": users})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# (필요하다면 통계 API 등도 여기에 추가)