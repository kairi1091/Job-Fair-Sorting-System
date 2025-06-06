# routes/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import pandas as pd
import os
from werkzeug.utils import secure_filename
from utils.data_loader import load_students, load_companies, get_department_id
from utils.assigner import assign_preferences, fill_with_industry_match, fill_zero_slots, run_pattern_a
import random
from flask import send_file
from utils.data_loader import load_students, load_companies
from utils.diagnoser import build_diagnosis


views = Blueprint("views", __name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}

NUM_SLOTS = 4

@views.route("/admin/run", methods=["POST"])
def run_assignment():
    from utils.data_loader import get_department_id
    df_preference, mode = load_students("data/students.csv")
    session["mode"] = mode
    df_company = load_companies("data/companies.csv")
    student_ids = df_preference["student_id"].unique()
    session["shared_capacity"] = int(request.form.get("shared_capacity", 10))
    cap = session["shared_capacity"]

    # 全体の結果用辞書
    student_schedule = {}
    student_score = {}
    student_assigned_companies = {}
    all_reason_logs = []
    filled_step4_total = 0
    filled_step5_total = 0
    # 各学科ごとのログ用辞書
    dept_log_summary = {}  # {dept: {"step4": X, "step5": Y}}
    cross_total = 0


    # 学科ごとにグループ化
    dept_to_students = {}
    for sid in student_ids:
        dept = get_department_id(sid)
        if dept is None:
            continue
        dept_to_students.setdefault(dept, []).append(sid)
        
    
    # 学科ループに入る前に diagnosis.csv をリセット
    if os.path.exists("diagnosis.csv"):
        os.remove("diagnosis.csv")


    # 各学科ごとに処理
    for dept, sids in dept_to_students.items():
        df_dept_company = df_company[df_company["department_id"] == dept]
        df_dept_pref = df_preference[df_preference["student_id"].isin(sids)]
                # 学科内の企業だけに限定する（重要！）
        valid_companies = df_dept_company["企業名"].tolist()
        df_dept_pref = df_dept_pref[df_dept_pref["company_name"].isin(valid_companies)]
        
        
        total_capacity = cap * len(df_dept_company) * NUM_SLOTS
        max_demand = len(sids) * NUM_SLOTS

        if total_capacity >= max_demand:
            pattern = "A"
        else:
            pattern = "B"
            

        if pattern == "A":
            schedule, score, assigned, capacity, filled4, filled5, reasons = run_pattern_a(
                df_dept_pref, df_dept_company, sids, cap, NUM_SLOTS
            )
            filled_step4_total += filled4
            
            filled_step5_total += filled5

            # マージ
            student_schedule.update(schedule)
            student_score.update(score)
            student_assigned_companies.update(assigned)
            all_reason_logs.append(reasons)
            
            matched_cnt = sum(
                1 for sid in sids
                if any(
                    c in df_dept_pref[df_dept_pref.student_id == sid].company_name.values
                    for c in schedule[sid]
                )
            )
            print(f"[{dept}] 希望一致学生数 = {matched_cnt} / {len(sids)}")
            # -----------------------------------------------
            dept_log_summary[dept] = {"step4": filled4, "step5": filled5}
            
            
            df_orig_pref_dept = df_preference[   # ← 学科で絞るだけ
                df_preference["student_id"].isin(sids)
            ]
            
            df_diag_dept, cross_pref, cross_assign = build_diagnosis(
                df_orig_pref_dept,   # ← フィルタしない元の希望 DF
                schedule,
                df_dept_company      # 割当学科の企業 DF
            )


            # ログ出力や集計
            if cross_pref:
                print(f"⚠️ {dept}: 学科外を希望した件数 = {len(cross_pref)}")
            if cross_assign:
                print(f"❌ {dept}: 学科外割当 {cross_assign[:10]} ...")  # 先頭 10 件だけ表示
            else:
                print(f"✅ {dept}: 学科外割当なし")


            # ---- 集計 ----
            cross_pref_cnt   = len(cross_pref)
            cross_assign_cnt = len(cross_assign)

            dept_log_summary[dept].update({
                "step4"        : filled4,
                "step5"        : filled5,
                "cross_pref"   : cross_pref_cnt,
                "cross_assign" : cross_assign_cnt,
            })

            cross_total += cross_assign_cnt
            df_diag_dept.to_csv(
                "diagnosis.csv",
                mode="a",            # 追記
                index=False,
                header=not os.path.exists("diagnosis.csv")  # 最初の学科だけヘッダ
            )
            
            print(f"[DEBUG] cross_pref={cross_pref_cnt}, cross_assign={cross_assign_cnt}")

        else:
            flash(f"⚠️ 学科 {dept} はパターンBのためスキップ（未実装）")
            print(f"⚠️ 学科 {dept} はパターンBのためスキップ（未実装）")
            dept_log_summary[dept] = {"step4": 0, "step5": 0}
            
        
    total_cross_assign = sum(dept_log_summary[d].get("cross_assign", 0)
                          for d in dept_log_summary)
    
    print(f"\n=== 全学科 cross_pref 合計: "
       f"{sum(d.get('cross_pref', 0) for d in dept_log_summary.values())} 件 ===")
    print(f"=== 全学科 cross_assign 合計: {total_cross_assign} 件 ===")



    # --- CSV出力 ---
    output_df = pd.DataFrame.from_dict(
        student_schedule, orient="index",
        columns=[f"slot_{i}" for i in range(NUM_SLOTS)]
    )
    output_df["score"] = output_df.index.map(lambda sid: student_score.get(sid, 0))
    output_df.reset_index(names="student_id", inplace=True)
    output_df.to_csv("schedule.csv", index=False)
    flash("割当を実行し、schedule.csvを更新しました。")

    # --- logs.txt 出力 ---
    with open("logs.txt", "w", encoding="utf-8") as logf:
        logf.write(f"STEP 4: 学科マッチ補完数（合計） = {filled_step4_total}\n")
        logf.write(f"STEP 5: 0人スロット補完数（合計） = {filled_step5_total}\n")
        logf.write("\n--- 学科別 補完内訳 ---\n")
        for dept, counts in dept_log_summary.items():
            logf.write(f"学科 {dept} → STEP4: {counts['step4']}件, STEP5: {counts['step5']}件\n")

        logf.write("\n--- 補完理由一覧 ---\n")
        for reason_logs in all_reason_logs:
            for sid, slot_reason in reason_logs.items():
                for slot, reason in slot_reason.items():
                    logf.write(f"{sid} の slot_{slot}：{reason}\n")

        logf.write("\n--- 学科外希望／割当件数 ---\n")
        for dept, counts in dept_log_summary.items():
            logf.write(
                f"学科 {dept} → cross_pref = {counts.get('cross_pref',0)} 件, "
                f"cross_assign = {counts.get('cross_assign',0)} 件\n"
            )
        logf.write(f"\n全学科合計 cross_assign = {cross_total} 件\n")

                    

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
        
    # ★★ ここから診断サマリを追加 ★★
    try:
        df_diag = pd.read_csv("diagnosis.csv")
        summary = df_diag.groupby(["dept", "result"]).size().unstack(fill_value=0)
        diag_table = summary.to_html(classes="table table-bordered")
    except Exception:
        diag_table = "<p>diagnosis.csv が存在しません</p>"

    # render_template に diag_table を渡す
    return render_template(
        "logs.html",
        step_logs=step_logs,
        violation_logs=violation_logs,
        diag_table=diag_table     # ← 追加
    )
