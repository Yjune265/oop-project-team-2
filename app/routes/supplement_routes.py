from flask import Blueprint, request, jsonify
from app.services.supplement_api import search_supplement


supplement_bp = Blueprint("supplement_bp", __name__)


@supplement_bp.route("/search", methods=["GET"])
def supplement_search():
    keyword = request.args.get("q")
    return jsonify(search_supplement(keyword))