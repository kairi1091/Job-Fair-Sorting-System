# routes/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import pandas as pd
import os
from werkzeug.utils import secure_filename
from utils.data_loader import load_students, load_companies, get_department_id
from utils.assigner import assign_preferences, fill_with_industry_match, fill_with_random
import random
from flask import send_file
from utils.data_loader import load_students, load_companies


views = Blueprint("views", __name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}

NUM_SLOTS = 4

@views.route("/admin/run", methods=["POST"])
def run_assignment():
    df_preference, mode = load_students("data/students.csv")
    session["mode"] = mode  # ← モードを保存
    df_company = load_companies("data/companies.csv")
    student_ids = df_preference["student_id"].unique()

    # モードを保存
    session["mode"] = int(request.form.get("mode", 1))
    mode = session["mode"]

    # 共通キャパを保存
    session["shared_capacity"] = int(request.form.get("shared_capacity", 10))
    cap = session["shared_capacity"]

    # 初期化
    student_schedule = {sid: [None] * NUM_SLOTS for sid in student_ids}
    student_score = {sid: 0 for sid in student_ids}
    student_assigned_companies = {sid: set() for sid in student_ids}

    # すべての企業に共通キャパを設定
    company_capacity = {
        cname: [cap] * NUM_SLOTS for cname in df_company["企業名"]
    }

    # 希望ランク別に割当
    for rank in range(1, 4):
        df_ranked = df_preference[df_preference["rank"] == rank]
        assign_preferences(
            df_ranked, point=(4 - rank),
            student_schedule=student_schedule,
            student_score=student_score,
            student_assigned_companies=student_assigned_companies,
            company_capacity=company_capacity,
            num_slots=NUM_SLOTS,
            mode=mode,
            phase_label=f"第{rank}希望"
        )

    # STEP 4: 業種マッチ補完
    filled_step4 = fill_with_industry_match(
        student_schedule, student_assigned_companies,
        company_capacity, df_company, NUM_SLOTS
    )
    flash(f"STEP 4: 学科マッチで {filled_step4} スロット補完しました。")

    # STEP 5: ランダム補完
    filled_step5 = fill_with_random(
        student_schedule, student_assigned_companies,
        company_capacity, NUM_SLOTS
    )
    flash(f"STEP 5: ランダムで {filled_step5} スロット補完しました。")

    # CSV出力
    output_df = pd.DataFrame.from_dict(
        student_schedule, orient="index",
        columns=[f"slot_{i}" for i in range(NUM_SLOTS)]
    )
    output_df["score"] = output_df.index.map(lambda sid: student_score[sid])
    if mode == 1:
        output_df["slot_3"] = "自由訪問枠"

    output_df.reset_index(names="student_id", inplace=True)
    output_df.to_csv("schedule.csv", index=False)
    flash("割当を実行し、schedule.csvを更新しました。")

    with open("logs.txt", "w", encoding="utf-8") as logf:
        logf.write(f"STEP 4: 学科マッチ補完数 = {filled_step4}\n")
        logf.write(f"STEP 5: ランダム補完数 = {filled_step5}\n")

    return redirect(url_for("views.admin"))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_schedule():
    return pd.read_csv("schedule.csv")

@views.route("/admin/download")
def download_schedule():
    path = "schedule.csv"
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    flash("スケジュールファイルが存在しません。")
    return redirect(url_for("views.admin"))

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
    from utils.data_loader import load_companies

    df_company = load_companies("data/companies.csv")
    companies = df_company["企業名"].tolist()

    # 現在のモードとキャパをセッションから取得
    current_mode = session.get("mode", 1)
    shared_capacity = session.get("shared_capacity", 10)

    try:
        df = pd.read_csv("schedule.csv")
        return render_template("admin.html",
                               table=df.to_html(classes="table table-bordered", index=False),
                               current_mode=current_mode,
                               shared_capacity=shared_capacity)
    except Exception:
        return render_template("admin.html",
                               table="<p>まだ割当が実行されていません</p>",
                               current_mode=current_mode,
                               shared_capacity=shared_capacity)



@views.route("/admin/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        students_file = request.files.get("students")
        companies_file = request.files.get("companies")

        # 保存先パス
        students_path = os.path.join(UPLOAD_FOLDER, "students.csv")
        companies_path = os.path.join(UPLOAD_FOLDER, "companies.csv")

        # エラーチェック
        if not students_file or not allowed_file(students_file.filename):
            flash("⚠️ 学生CSVファイルが正しく選択されていません")
            return redirect(request.url)

        if not companies_file or not allowed_file(companies_file.filename):
            flash("⚠️ 企業CSVファイルが正しく選択されていません")
            return redirect(request.url)

        # ファイル保存
        students_file.save(students_path)
        companies_file.save(companies_path)

        # クレンジング後の件数確認
        try:
            df_students, mode = load_students("data/students.csv")

            df_companies = pd.read_csv(companies_path)
            df_companies = df_companies[df_companies["企業名"].notna()]
            df_companies = df_companies[df_companies["企業名"].str.strip() != ""]
            df_companies["企業名"] = df_companies["企業名"].str.strip()
            df_companies.to_csv(companies_path, index=False)

            # ✅ 学生数カウント（学籍番号または student_id）
            possible_keys = ["学籍番号", "student_id"]
            for key in possible_keys:
                if key in df_students.columns:
                    n_students = df_students[key].nunique()
                    break
            else:
                n_students = "不明（列名が見つかりません）"

            mode_msg = "3枠希望（＋自由訪問）" if mode == 1 else "4枠すべて希望"
            flash(f"✅ 学生データ：{n_students}人 ／ 企業データ：{len(df_companies)}社 をアップロードしました（モード：{mode_msg}）")

        except Exception as e:
            flash(f"⚠️ ファイル保存後の読み込みでエラーが発生しました：{str(e)}")


        return redirect(url_for("views.upload_file"))

    return render_template("upload.html")

# 統計
@views.route("/admin/stats")
def stats():
    try:
        df_schedule = pd.read_csv("schedule.csv")
        df_pref = pd.read_csv("data/students.csv")
        df_company = load_companies("data/companies.csv")  # ← 修正ポイント
    except Exception as e:
        flash("必要なCSVファイルが読み込めませんでした")
        return redirect(url_for("views.admin"))

    # 希望企業リスト作成（rank付き）
    pref_list = []
    for _, row in df_pref.iterrows():
        for rank in range(1, 4):
            company = row.get(f"希望事業所{rank}")
            if pd.notna(company):
                pref_list.append({
                    "student_id": row["学籍番号"],
                    "company_name": company.strip(),
                    "rank": rank
                })
    df_preference = pd.DataFrame(pref_list)

    stats_data = []
    preferred_ids = df_preference["student_id"].unique()

    for _, row in df_schedule.iterrows():
        sid = row["student_id"]
        assigned = [row[f"slot_{i}"] for i in range(4) if f"slot_{i}" in row]
        assigned = [a for a in assigned if pd.notna(a) and a != "自由訪問枠"]

        preferred_rows = df_preference[df_preference["student_id"] == sid]
        preferred = preferred_rows["company_name"].unique().tolist()

        if not preferred:
            continue  # 希望なしは除外

        matched = [a for a in assigned if a in preferred]
        reflect_rate = 100 if matched else 0

        stats_data.append({
            "student_id": sid,
            "assigned": assigned,
            "matched": matched,
            "reflect_rate": reflect_rate
        })

    return render_template("stats.html", stats_data=stats_data)


@views.route("/admin/logs")
def logs():
    try:
        with open("logs.txt", "r", encoding="utf-8") as f:
            step_logs = f.read().splitlines()
    except FileNotFoundError:
        step_logs = ["ログファイルが存在しません"]

    # schedule.csv のチェック
    try:
        df_schedule = pd.read_csv("schedule.csv")
        from utils.data_loader import get_department_id
        from utils.logger import check_schedule_violations

        student_schedule = {
            row["student_id"]: [row.get(f"slot_{i}") for i in range(4)]
            for _, row in df_schedule.iterrows()
        }

        df_company = pd.read_csv("data/companies.csv")
        company_capacity = {
            row["企業名"]: [int(row.get(f"slot_{i}", 0)) for i in range(4)]
            for _, row in df_company.iterrows()
        }

        violation_logs = check_schedule_violations(student_schedule, company_capacity)

    except Exception:
        violation_logs = ["schedule.csv の読み込みまたは検査に失敗しました"]

    return render_template("logs.html", step_logs=step_logs, violation_logs=violation_logs)
