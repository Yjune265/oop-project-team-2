# 원래 app.py였으나 app 폴더와 이름 충돌로 run.py로 이름 변경

from flask import Flask, render_template
from config import Config  # ✅ config.py 파일에서 설정 클래스 불러오기
from app.routes import register_blueprints

def create_app():
    # 1. Flask 앱 생성 (HTML, CSS 폴더 위치 지정)
    app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
    
    # 2. config.py에 있는 설정 적용 (SECRET_KEY 등)
    app.config.from_object(Config)
    
    # 3. [추가] JSON 응답 시 한글 깨짐 방지 설정
    app.config['JSON_AS_ASCII'] = False
    
    # 4. 블루프린트(기능들) 등록
    register_blueprints(app)

    # 5. 메인 페이지 라우트 설정
    @app.route("/")
    def index():
        # "Running" 글자 대신, 우리가 만든 메인 화면(HTML)을 보여줍니다.
        return render_template("index.html")
    
    # ==========================================
    # 👇 아래 내용을 추가해주세요! (빈 껍데기 메뉴들)
    # ==========================================

    @app.route("/login")
    def login():
        return "<h1>로그인 페이지 (준비중)</h1>"

    @app.route("/register")
    def register():
        return "<h1>회원가입 페이지 (준비중)</h1>"

    @app.route("/logout")
    def logout():
        return "<h1>로그아웃 기능 (준비중)</h1>"

    @app.route("/mypage")
    def my_page():
        return "<h1>마이페이지 (준비중)</h1>"

    @app.route("/survey/step1")
    def survey_step1():
        return "<h1>설문조사 1단계 (준비중)</h1>"

    return app

if __name__ == "__main__":
    app = create_app()
    print("🚀 NutriGuide 서버가 시작되었습니다! http://127.0.0.1:5000")
    app.run(debug=True)