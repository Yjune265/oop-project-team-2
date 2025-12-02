# app/routes/survey_routes.py
from flask import Blueprint, request, render_template, jsonify
import json
from app.services.app_logic import UserProfileManager, RecommendationEngine

survey_bp = Blueprint("survey_bp", __name__)

@survey_bp.route("/submit", methods=["POST"])
def submit_survey():
    try:
        # 1. 폼 데이터 수신 (request.json이 아니라 request.form 사용)
        # 프론트엔드가 보낸 JSON '문자열'을 받습니다.
        user_profile_str = request.form.get('user_profile_json', '{}')
        health_concerns_str = request.form.get('health_concerns_json', '[]')
        medications_str = request.form.get('medications_json', '[]')

        # 2. 데이터 파싱 (문자열 -> 파이썬 딕셔너리/리스트 변환)
        user_profile = json.loads(user_profile_str)
        health_concerns = json.loads(health_concerns_str)
        medications = json.loads(medications_str)
        
        # UserProfileManager가 좋아하는 구조로 정리
        # (특이체질 정보는 user_profile 안에 들어있으므로 꺼내서 최상위로 맞춤)
        special_conditions = user_profile.get('specialConditions', [])
        
        survey_data = {
            "userProfile": user_profile,
            "healthConcerns": health_concerns,
            "medications": medications,
            "specialConditions": special_conditions
        }
        
        # 3. 데이터 저장 (UserProfileManager)
        profile_mgr = UserProfileManager()
        user_id = profile_mgr.save_survey_data(survey_data)
        
        # 4. 추천 알고리즘 실행 (RecommendationEngine)
        rec_engine = RecommendationEngine(user_id)
        results = rec_engine.run_recommendation()
        
        # 5. 결과 화면 렌더링 (핵심 수정 ⭐)
        # JSON을 반환하는 게 아니라, result.html에 데이터를 담아서 보여줍니다.
        # results['recommendations'] 리스트를 'recommendations'라는 이름으로 넘김
        return render_template("result.html", recommendations=results['recommendations'])
        
    except Exception as e:
        # 에러 발생 시 디버깅을 위해 에러 메시지 출력
        print(f"❌ 설문 분석 중 오류 발생: {e}")
        return f"<h1>분석 중 오류가 발생했습니다.</h1><p>{str(e)}</p>", 500