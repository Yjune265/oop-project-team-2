from flask import Blueprint, jsonify
from app.services.admin_logic import AdminManager


admin_bp = Blueprint("admin_bp", __name__)
admin_manager = AdminManager()


@admin_bp.route("/users", methods=["GET"])
def list_users():
    return jsonify(admin_manager.list_all_users())