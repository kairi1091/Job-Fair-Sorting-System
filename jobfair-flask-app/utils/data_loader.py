import pandas as pd
import re

import os, pathlib
print("students.csv =", pathlib.Path("data/students.csv").resolve().exists())
print("companies.csv =", pathlib.Path("data/companies.csv").resolve().exists())
df_raw = pd.read_csv("data/students.csv", nrows=0, encoding="utf-8")
print("Cols:", list(df_raw.columns))
import pathlib, os, pandas as pd, datetime as dt

PATH = pathlib.Path("data/students.csv").resolve()
print(">>> 読み込んでいるパス:", PATH)
print(">>> 更新日時:", dt.datetime.fromtimestamp(PATH.stat().st_mtime))

# ついでに 1 行目を直接表示
with open(PATH, "r", encoding="utf-8") as f:
    print(">>> 先頭行:", f.readline().strip())
import glob
candidates = glob.glob("**/students*.csv", recursive=True)
print(">>> 見つかった CSV:", candidates)

# --------------------- 学生 ---------------------
def load_students(path="data/students.csv", mode=None):
    df = pd.read_csv(path, encoding="utf-8")
    def _normalize(col: str) -> str:
        return (
            col.replace("\ufeff", "")   # BOM 除去
            .replace("　", "")       # 全角スペース
            .strip()                 # 前後半角スペース
        )

    print(">>> after read_csv", df.shape)
    df.columns = [_normalize(c) for c in df.columns]
    print(">>> after normalize", list(df.columns))
    print(df.head(3))
    # ←★ 列名の空白除去

    # --- 列名自動検出 ---
    def pick(colnames, candidates, label):
        hits = [c for c in colnames if c in candidates]
        if not hits:
            raise ValueError(f"列 '{label}' が見つかりません。候補={candidates}")
        return hits[0]

    dept_col = pick(df.columns, ["学科名", "department_name"], "学科名")
    id_col   = pick(df.columns, ["学籍番号", "student_id"], "学籍番号")

    # --- 希望列を抽出（“第一希望”などを含む列） ---
    pref_cols = [c for c in df.columns if re.match(r"第?[一二三四]希望", c)]
    if not pref_cols:
        raise ValueError("『第一希望〜第三(四)希望』列が見つかりません")
    pref_cols = sorted(pref_cols, key=lambda s: "一二三四".index(re.findall(r"[一二三四]", s)[0]))

    # --- 整形 ---
    pref_list, student_dept_map = [], {}
    for _, row in df.iterrows():
        sid  = str(row[id_col]).strip()
        dept = str(row[dept_col]).strip()
        student_dept_map[sid] = dept

        for rank, col in enumerate(pref_cols, 1):
            company = str(row[col]).replace("\n", " ").strip()  # 改行→空白
            if company and company.lower() != "nan":
                pref_list.append({"student_id": sid,
                                  "company_name": company,
                                  "rank": rank})

    df_pref = pd.DataFrame(pref_list)
    mode = 4 if len(pref_cols) >= 4 else 3
    print("pref_cols =", pref_cols)
    return df_pref, mode, student_dept_map

# --------------------- 企業 ---------------------
def load_companies(path="data/companies.csv"):
    df = pd.read_csv(path, encoding="utf-8")
    def _normalize(col: str) -> str:
        return (
            col.replace("\ufeff", "")   # BOM 除去
            .replace("　", "")       # 全角スペース
            .strip()                 # 前後半角スペース
        )

    df.columns = [_normalize(c) for c in df.columns]

    # 列名検出
    company_col = [c for c in df.columns if c in ["企業名", "事業所名", "company_name"]]
    dept_col    = [c for c in df.columns if c in ["学科名", "department_id", "業種"]]
    if not company_col or not dept_col:
        raise ValueError("企業CSVに『企業名』または『学科名』列がありません")
    company_col, dept_col = company_col[0], dept_col[0]

    # 整形
    df = df[[company_col, dept_col]].copy()
    df[company_col] = df[company_col].astype(str).str.strip()
    df = df[df[company_col].ne("")]
    df = df.rename(columns={company_col: "company_name",
                            dept_col: "department_id"})
    return df