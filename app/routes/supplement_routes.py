# app/routes/supplement_routes.py
# SQLite DB 연동 기반 영양제 검색 API (MVP 완성 버전)

from flask import Blueprint, request, jsonify
from app.models.database import fetch_all

supplement_bp = Blueprint("supplement_bp", __name__)


# ===============================
# 1) 제품명 기반 기본 검색
# ===============================
@supplement_bp.route("/search", methods=["GET"])
def search_supplement():
    """
    제품명(product_name) 기반 기본 검색 (부분 일치)
    예: /api/supplement/search?q=비타민
    반환: 최대 20개
    """
    keyword = request.args.get("q", "")

    if not keyword:
        return jsonify({"error": "검색어(q)가 필요합니다."}), 400

    query = """
        SELECT id, product_name, company, ingredients
        FROM supplements
        WHERE product_name LIKE ?
        ORDER BY id DESC
        LIMIT 20
    """

    results = fetch_all(query, [f"%{keyword}%"])

    return jsonify({
        "keyword": keyword,
        "count": len(results),
        "results": results
    })


# ===============================
# 2) 성분 기반 검색 (ingredients 컬럼)
# ===============================
@supplement_bp.route("/ingredient", methods=["GET"])
def search_by_ingredient():
    """
    성분(ingredients) 기반 검색
    예: /api/supplement/ingredient?q=아연
    """
    keyword = request.args.get("q", "")

    if not keyword:
        return jsonify({"error": "검색어(q)가 필요합니다."}), 400

    query = """
        SELECT id, product_name, company, ingredients
        FROM supplements
        WHERE ingredients LIKE ?
        LIMIT 20
    """

    results = fetch_all(query, [f"%{keyword}%"])

    return jsonify({
        "keyword": keyword,
        "count": len(results),
        "results": results
    })


# ===============================
# 3) 제품명 + 성분 동시 검색 (AND 조건)
# ===============================
@supplement_bp.route("/advanced", methods=["GET"])
def advanced_search():
    """
    고급 검색: 제품명 + 성분 동시 검색
    예: /api/supplement/advanced?name=비타민&ing=아연
    둘 중 하나만 넣어도 검색됨.
    """

    name_kw = request.args.get("name", "")
    ing_kw = request.args.get("ing", "")

    # 조건 구성
    conditions = []
    params = []

    if name_kw:
        conditions.append("product_name LIKE ?")
        params.append(f"%{name_kw}%")

    if ing_kw:
        conditions.append("ingredients LIKE ?")
        params.append(f"%{ing_kw}%")

    if not conditions:
        return jsonify({"error": "검색 조건(name 또는 ing)이 필요합니다."}), 400

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT id, product_name, company, ingredients
        FROM supplements
        WHERE {where_clause}
        LIMIT 20
    """

    results = fetch_all(query, params)

    return jsonify({
        "name_keyword": name_kw,
        "ingredient_keyword": ing_kw,
        "count": len(results),
        "results": results
    })
