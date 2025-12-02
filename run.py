from flask import Flask, render_template, request, session, redirect, url_for
from config import Config  # config.py에서 설정 불러오기
from app.routes import register_blueprints

def create_app():
    # 1. Flask 앱 생성 (HTML, CSS 폴더 위치 지정)
    app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
    
    # 2. config.py 설정 적용
    app.config.from_object(Config)
    
    # 3. 한글 깨짐 방지
    app.config['JSON_AS_ASCII'] = False
    
    # 4. 블루프린트 등록
    register_blueprints(app)

    # ==========================================
    # 👇 메인 및 인증 라우트 (프리패스 적용)
    # ==========================================

    @app.route("/")
    def index():
        return render_template("index.html")
    
    # [로그인] 무조건 통과!
    @app.route("/login", methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            # 폼에서 입력한 아이디 가져오기 (비번은 확인 안 함)
            user_id = request.form.get('user_id')
            
            # 세션에 "이 사람 로그인했음" 도장 찍기
            session['user_id'] = user_id
            session['user_name'] = "체험단"  # 이름은 고정값 (원하면 form에서 받아도 됨)
            
            # 메인 페이지로 이동
            return redirect(url_for('index'))
            
        return render_template("login.html")

    # [회원가입] 하는 척하고 로그인 페이지로 보냄
    @app.route("/register", methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            return redirect(url_for('login'))
        return render_template("register.html")

    # [로그아웃] 세션 지우기
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for('index'))

    # ==========================================
    # 👇 기타 페이지 연결
    # ==========================================

    @app.route("/mypage")
    def my_page():
        return render_template("mypage.html")

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

    return app

if __name__ == "__main__":
    app = create_app()
    print("🚀 NutriGuide 서버가 시작되었습니다! http://127.0.0.1:5000")
    app.run(debug=True)