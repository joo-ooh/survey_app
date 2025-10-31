from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import csv, os, sys, io
from collections import Counter, defaultdict
from urllib.parse import urlparse
import psycopg2

app = Flask(__name__)

DATA_FILE = "survey_data.csv"

# PyInstaller 환경 대응 경로 처리
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)

# 초기 CSV 생성 (헤더)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "gender", "age", "consent"])

# Render Internal Database URL 가져오기
DATABASE_URL = os.environ.get("DATABASE_URL")

# PostgreSQL 연결용 함수
def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL 환경변수가 설정되지 않았습니다.")
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    return conn

# 초기 테이블 생성
if DATABASE_URL:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            gender TEXT NOT NULL,
            age TEXT NOT NULL,
            consent TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# 기본 라벨 순서
AGE_ORDER = ["0~8", "9~13", "14~16", "17~19", "20~24", "성인"]
GENDER_ORDER = ["남성", "여성"]

# 설문결과 저장 리스트
survey_results = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/survey", methods=["GET", "POST"])
def survey():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        gender = request.form.get("gender", "").strip()
        age = request.form.get("age", "").strip()
        consent = request.form.get("consent", "").strip()

        if not name or not gender or not age or not consent:
            return "입력값이 부족합니다.", 400

        # CSV에 저장
        with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([name, gender, age, consent])

        # 메모리에도 저장
        result = {"name": name, "gender": gender, "age": age, "consent": consent}
        survey_results.append(result)

        # PostgreSQL에 저장
        if DATABASE_URL:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO responses (name, gender, age, consent) VALUES (%s, %s, %s, %s)",
                    (name, gender, age, consent)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB 저장 오류: {e}")

        return redirect(url_for("thankyou"))
    return render_template("survey.html")

@app.route("/thankyou")
def thankyou():
    return render_template("thankyou.html")

@app.route("/result")
def result():
    # CSV 읽기
    data = []
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT name, gender, age, consent FROM responses")
            rows = cur.fetchall()
            for row in rows:
                data.append({
                    "name": row[0],
                    "gender": row[1],
                    "age": row[2],
                    "consent": row[3]
                })
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB 읽기 오류: {e}")
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 4: 
                    data.append({
                        "name": row[0].strip(),
                        "gender": row[1].strip(),
                        "age": row[2].strip(),
                        "consent": row[3].strip()
                    })

    # 집계 초기화
    gender_counts = Counter()
    age_counts = Counter()
    consent_counts = Counter()
    gender_age_data = defaultdict(lambda: defaultdict(int))

    # 데이터 통계 계산
    for row in data:
        g = row["gender"] or "미상"
        a = row["age"] or "미상"
        c = row["consent"] or "미상"
        gender_counts[g] += 1
        age_counts[a] += 1
        consent_counts[c] += 1
        gender_age_data[g][a] += 1

    # 나이/성별 라벨 정렬
    age_labels = AGE_ORDER.copy()
    for a in age_counts.keys():
        if a not in age_labels:
            age_labels.append(a)

    gender_labels = [g for g in GENDER_ORDER if g in gender_counts]
    for g in gender_counts:
        if g not in gender_labels:
            gender_labels.append(g)

    # 차트용 배열
    gender_values = [gender_counts.get(g, 0) for g in gender_labels]
    age_values = [age_counts.get(a, 0) for a in age_labels]
    consent_labels = list(consent_counts.keys())
    consent_values = [consent_counts.get(k, 0) for k in consent_labels]

    # 성별-나이대 데이터 구성
    gender_age_chart_data = {}
    for g in gender_labels:
        gender_age_chart_data[g] = [gender_age_data[g].get(a, 0) for a in age_labels]

    total_responses = len(data)

    return render_template(
        "result.html",
        total_responses=total_responses,
        results=data,
        gender_counts=gender_counts,
        age_counts=age_counts,
        consent_counts=consent_counts,
        gender_age_data=gender_age_data,
        age_labels=age_labels,
        gender_labels=gender_labels,
        gender_values=gender_values,
        age_values=age_values,
        consent_labels=consent_labels,
        consent_values=consent_values,
        gender_age_chart_data=gender_age_chart_data
    )

@app.route("/reset", methods=["POST"])
def reset():
    admin_pw = request.form.get("admin_password", "")
    correct_pw = "admin123"  # ✅ 실제 사용할 비밀번호를 여기에 지정하세요

    if admin_pw != correct_pw:
        # 비밀번호가 틀렸을 경우
        return render_template("wrong_password.html")

    # 비밀번호가 맞을 경우 -> CSV 초기화
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "gender", "age", "consent"])
    
    # PostgreSQL 초기화
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM responses")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB 초기화 오류: {e}")

    return render_template("reset_done.html")

@app.route("/download_csv")
def download_csv():
    data = []

    # 1. PostgreSQL에서 데이터 가져오기
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT name, gender, age, consent FROM responses")
            rows = cur.fetchall()
            for row in rows:
                data.append(row)
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB 읽기 오류: {e}")
            # DB 오류 발생 시 CSV 파일에서 읽도록 fallback
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, newline="", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        next(reader, None)  # 헤더 건너뛰기
                        for row in reader:
                            data.append(row)
                except Exception as f_err:
                    print(f"CSV 읽기 오류: {f_err}")
                    return "데이터를 가져올 수 없습니다.", 500
            else:
                return "데이터가 없습니다.", 404

    # 2. DATABASE_URL이 없는 경우 → CSV 파일에서 읽기
    elif os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # 헤더 건너뛰기
                for row in reader:
                    data.append(row)
        except Exception as e:
            print(f"CSV 읽기 오류: {e}")
            return "데이터를 가져올 수 없습니다.", 500
    else:
        return "데이터가 없습니다.", 404

    # 3. CSV 생성 (UTF-8 BOM 포함)
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["이름", "성별", "나이", "개인정보 동의"])  # 헤더
        writer.writerows(data)
        output.seek(0)

        # ✅ UTF-8 BOM 추가 (Excel에서 한글 깨짐 방지)
        csv_with_bom = "\ufeff" + output.getvalue()
    except Exception as e:
        print(f"CSV 생성 오류: {e}")
        return "CSV를 생성할 수 없습니다.", 500

    # 4. 파일 다운로드
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="survey_export.csv"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)