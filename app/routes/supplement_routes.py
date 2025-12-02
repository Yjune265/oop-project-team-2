# app/routes/supplement_routes.py
from flask import Blueprint, request, jsonify, render_template
from app.services.app_logic import SearchEngine 
import random

supplement_bp = Blueprint("supplement_bp", __name__)

# ==========================================
# 1. 카테고리 그룹 매핑 (절대 지우면 안 됨!)
# ==========================================
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

# ==========================================
# 2. 페이지 렌더링 라우트
# ==========================================
@supplement_bp.route("/search")
def search_page():
    return render_template("search.html")


# ==========================================
# 3. API 라우트 (데이터 제공)
# ==========================================
@supplement_bp.route("/category", methods=["GET"])
def search_category_api():
    try:
        # 1. 파라미터 받기 (팀원의 q와 우리의 name 모두 지원)
        category_name = request.args.get("name") or request.args.get("q", "")
        limit = request.args.get("limit", 10, type=int) 
        page = request.args.get("page", 1, type=int)    # 팀원이 추가한 page 파라미터
        
        if not category_name:
            return jsonify({"status": "error", "message": "카테고리 이름이 필요합니다."}), 400

        # 2. Offset 계산 (팀원 로직 적용)
        offset = (page - 1) * limit

        engine = SearchEngine()
        results = []

        # 3. 매핑된 키워드 찾기 (우리 로직)
        target_keywords = CATEGORY_GROUP_MAP.get(category_name, [category_name])

        # 4. DB 검색 (충분히 많이 가져오기 위해 limit을 크게 잡음)
        # 페이징을 위해선 일단 넉넉히 가져온 뒤 파이썬에서 자르는 게 편함
        for keyword in target_keywords:
            products = engine.search_products_by_category(keyword, limit=100) 
            results.extend(products)

        # 5. 결과 섞기 & 중복 제거
        # (주의: 랜덤 셔플을 하면 '더보기' 눌렀을 때 아까 본 게 또 나올 수도 있습니다.
        #  하지만 다양한 제품 노출을 위해 셔플 유지. 싫으면 아래 줄 삭제)
        random.shuffle(results)
        
        unique_results = list({v['id']: v for v in results}.values())
        
        # 6. 페이징 처리 (팀원의 슬라이싱 로직 적용)
        # 전체 리스트에서 이번 페이지에 보여줄 만큼만 뚝 떼어냄
        paged_results = unique_results[offset : offset + limit]
        
        return jsonify({
            "status": "success", 
            "page": page,
            "count": len(paged_results), 
            "total_count": len(unique_results), # 전체 개수도 알려주면 좋음
            "results": paged_results
        })

    except Exception as e:
        print(f"❌ 카테고리 검색 중 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


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