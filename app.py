from flask import Flask, render_template, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "your_secret_key"   # 세션 사용하려면 필요함

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    # 나중에 구현할 예정
    return "로그인 페이지 준비 중"

@app.route('/register')
def register():
    return "회원가입 페이지 준비 중"

@app.route('/survey/step1')
def survey_step1():
    return "설문 Step 1 준비 중"

@app.route('/mypage')
def my_page():
    return "마이페이지 준비 중"

if __name__ == '__main__':
    app.run(debug=True)
