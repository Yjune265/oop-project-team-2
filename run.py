from flask import Flask, render_template
from config import Config 
from app.routes import register_blueprints

def create_app():
    # 1. Flask 앱 생성 (templates와 static 폴더 위치 지정)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # 2. 설정 적용
    app.config.from_object(Config)
    app.config['JSON_AS_ASCII'] = False
    
    # 3. 블루프린트(기능들) 등록
    register_blueprints(app)

    # 4. 페이지 라우팅 연결
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/register")
    def register():
        return render_template("register.html")

    @app.route("/search")
    def search():
        return render_template("search.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/survey/step1")
    def survey_step1():
        return render_template("survey_step1.html")

    @app.route("/survey/step2")
    def survey_step2():
        return render_template("survey_step2.html")

    @app.route("/survey/step3")
    def survey_step3():
        return render_template("survey_step3.html")

    @app.route("/result")
    def result():
        return render_template("result.html")
        
    @app.route("/mypage")
    def my_page():
        # 마이페이지 HTML이 있다면 render_template으로 변경
        return "마이페이지 준비 중" 

    return app

if __name__ == "__main__":
    app = create_app()
    print("🚀 NutriGuide 서버 실행: http://127.0.0.1:5000")
    app.run(debug=True)