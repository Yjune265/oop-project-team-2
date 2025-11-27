from flask import Blueprint, request, jsonify
from app.services.app_logic import UserProfileManager


user_bp = Blueprint("user_bp", __name__)


@user_bp.route("/profile", methods=["POST"])
def save_profile():
    data = request.json
    manager = UserProfileManager()
    result = manager.save_user_profile(data)
    return jsonify({"saved": result})