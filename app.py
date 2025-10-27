from flask import Flask, render_template, request, redirect, url_for
import csv, sqlite3
import os
from collections import Counter, defaultdict
import sys

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

        return redirect(url_for("thankyou"))
    return render_template("survey.html")

@app.route("/thankyou")
def thankyou():
    return render_template("thankyou.html")

@app.route("/result")
def result():
    # CSV 읽기
    data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            for row in reader:
                if len(row) >= 4: 
                    data.append({
                        # 인덱스를 사용하여 명확하게 매핑
                        "name": row[0].strip(),
                        "gender": row[1].strip(),
                        "age": row[2].strip(),
                        "consent": row[3].strip()
                    })
                # 혹시 데이터가 잘못된 경우 대비
                else:
                    print(f"경고: 잘못된 형식의 데이터 행 감지 - {row}")

                # data.append({
                #     "name": row.get("name", "").strip(),
                #     "gender": row.get("gender", "").strip(),
                #     "age": row.get("age", "").strip(),
                #     "consent": row.get("consent", "").strip()
                # })


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
    return render_template("reset_done.html")

# 관리자 권한 없는 데이터 초기화 버튼
# @app.route("/reset", methods=["POST"])
# def reset():
#     # CSV 파일 초기화 (헤더만 남기기)
#     if os.path.exists(DATA_FILE):
#         with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow(["name", "gender", "age", "consent"])  # 헤더만 다시 작성
#     return render_template("reset_done.html")

if __name__ == "__main__":
    app.run(debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
