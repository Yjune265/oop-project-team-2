# app/routes/supplement_routes.py
from flask import Blueprint, request, jsonify
from app.services.app_logic import SearchEngine 
import random

# __init__.py에서 url_prefix="/api/supplement"로 설정되어 있음
supplement_bp = Blueprint("supplement_bp", __name__)

# ---------------------------------------------------------
# 1. 카테고리 그룹 매핑 (프론트엔드 그룹명 -> DB 키워드 변환)
# ---------------------------------------------------------
CATEGORY_GROUP_MAP = {
    "피로/활력": ["피로/활력"],
    "간 건강": ["간 건강"],
    "다이어트/체지방": ["다이어트/체지방"],
    "혈액순환/혈관": ["혈액순환/콜레스테롤", "혈압 관리", "혈당 관리"], 
    "눈 건강": ["눈 건강"],
    "뼈/관절": ["뼈/관절/근육"],
    "속 편한/소화": ["위/소화", "장 건강/변비"], 
    "피부/미용": ["피부", "모발/두피/손톱", "항노화/항산화"], 
    "면역력": ["면역력/알러지"],
    "수면/스트레스": ["수면 질 개선", "스트레스/마음건강", "기억력/인지력"], 
    "여성 건강": ["여성 건강/PMS", "임신/임신준비"], 
    "남성 건강": ["남성 건강"]
}

# ---------------------------------------------------------
# 2. API 라우트 (최종 주소: /api/supplement/category)
# ---------------------------------------------------------
@supplement_bp.route("/category", methods=["GET"])
def search_category_api():
    try:
        category_name = request.args.get("name", "")
        limit = request.args.get("limit", 10, type=int) 
        
        if not category_name:
            return jsonify({"status": "error", "message": "카테고리 이름이 필요합니다."}), 400

        engine = SearchEngine()
        results = []

        # 매핑된 키워드들로 DB 검색
        target_keywords = CATEGORY_GROUP_MAP.get(category_name, [category_name])

        for keyword in target_keywords:
            products = engine.search_products_by_category(keyword, limit=limit)
            results.extend(products)

        # 결과 섞기 및 중복 제거
        random.shuffle(results)
        unique_results = list({v['id']: v for v in results}.values())
        final_results = unique_results[:limit]
        
        return jsonify({
            "status": "success", 
            "count": len(final_results), 
            "results": final_results
        })

    except Exception as e:
        print(f"❌ 카테고리 검색 중 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# 제품 상세 조회 API (최종 주소: /api/supplement/detail/123)
@supplement_bp.route("/detail/<int:product_id>", methods=["GET"])
def product_detail_api(product_id):
    try:
        engine = SearchEngine()
        detail = engine.get_product_detail(product_id)
        
        if detail:
            return jsonify({"status": "success", "data": detail})
        else:
            return jsonify({"status": "fail", "message": "제품을 찾을 수 없습니다."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500