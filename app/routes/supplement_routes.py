# app/routes/supplement_routes.py
from flask import Blueprint, request, jsonify
# ✅ SQL 대신 저의 검색 로직 사용
from app.services.app_logic import SearchEngine 

supplement_bp = Blueprint("supplement_bp", __name__)

# 1. 카테고리 검색 (예: /api/supplement/category?q=간 건강)
@supplement_bp.route("/category", methods=["GET"])
def search_category():
    try:
        keyword = request.args.get("q", "")
        limit = request.args.get("limit", 20, type=int)
        
        engine = SearchEngine()
        # SearchEngine에 search_products_by_category 메서드가 있다고 가정
        results = engine.search_products_by_category(keyword, limit)
        
        return jsonify({"status": "success", "count": len(results), "results": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. 상세 조회 (예: /api/supplement/detail/123)
@supplement_bp.route("/detail/<int:product_id>", methods=["GET"])
def product_detail(product_id):
    try:
        engine = SearchEngine()
        detail = engine.get_product_detail(product_id)
        
        if detail:
            return jsonify({"status": "success", "data": detail})
        else:
            return jsonify({"status": "fail", "message": "제품 없음"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500