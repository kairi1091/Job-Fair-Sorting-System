# routes/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import pandas as pd
import os
from werkzeug.utils import secure_filename
from utils.data_loader import load_students, load_companies, get_department_id
from utils.assigner import assign_preferences, fill_with_industry_match, fill_with_random
import random


views = Blueprint("views", __name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}

NUM_SLOTS = 4
MODE = 1  # グローバル切替（自由訪問枠あり）

@views.route("/admin/run", methods=["POST"])
def run_assignment():
    # データ読み込み
    df_preference = load_students("data/students.csv")
    df_company = load_companies("data/companies.csv")
    student_ids = df_preference["student_id"].unique()

    # 初期化
    student_schedule = {sid: [None] * NUM_SLOTS for sid in student_ids}
    student_score = {sid: 0 for sid in student_ids}
    student_assigned_companies = {sid: set() for sid in student_ids}
    company_capacity = {
        row["企業名"]: [int(row.get(f"slot_{i}", 10)) for i in range(NUM_SLOTS)]
        for _, row in df_company.iterrows()
    }

    # 希望ランク別に割当（Step 1〜3）
    for rank in range(1, 4):
        df_ranked = df_preference[df_preference["rank"] == rank]
        assign_preferences(
            df_ranked, point=(4 - rank),
            student_schedule=student_schedule,
            student_score=student_score,
            student_assigned_companies=student_assigned_companies,
            company_capacity=company_capacity,
            num_slots=NUM_SLOTS,
            mode=MODE,
            phase_label=f"第{rank}希望"
        )
        

    # STEP 4: 学科マッチで空きスロット補完
    filled_step4 = fill_with_industry_match(
        student_schedule, student_assigned_companies,
        company_capacity, df_company, NUM_SLOTS
    )
    flash(f"STEP 4: 学科マッチで {filled_step4} スロット補完しました。")
    
    # STEP 5: 完全ランダム補完
    filled_step5 = fill_with_random(
        student_schedule, student_assigned_companies,
        company_capacity, NUM_SLOTS
    )
    flash(f"STEP 5: ランダムで {filled_step5} スロット補完しました。")

    # DataFrameにしてCSV出力
    output_df = pd.DataFrame.from_dict(
        student_schedule, orient="index",
        columns=[f"slot_{i}" for i in range(NUM_SLOTS)]
    )
    output_df["score"] = output_df.index.map(lambda sid: student_score[sid])
    if MODE == 1:
        output_df["slot_3"] = "自由訪問枠"

    output_df.reset_index(names="student_id", inplace=True)
    output_df.to_csv("schedule.csv", index=False)
    flash("割当を実行し、schedule.csvを更新しました。")
    return redirect(url_for("views.admin"))

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_schedule():
    return pd.read_csv("schedule.csv")

@views.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        student_id = request.form["student_id"]
        df = load_schedule()
        row = df[df["student_id"] == student_id]
        return render_template("result.html", row=row)
    return render_template("index.html")

@views.route("/admin")
def admin():
    try:
        df = pd.read_csv("schedule.csv")
        return render_template("admin.html", table=df.to_html(index=False))
    except Exception:
        return render_template("admin.html", table="<p>まだ割当が実行されていません</p>")


@views.route("/admin/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("ファイルが選択されていません")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("ファイル名が空です")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            os.replace(filepath, "schedule.csv")
            flash("スケジュールCSVを更新しました")
            return redirect(url_for("views.admin"))
        flash("CSVファイルのみアップロード可能です")
        return redirect(request.url)
    return render_template("upload.html")
