import pandas as pd
import re
import os
from pandas.errors import EmptyDataError
import pathlib, datetime as dt

# --------------------- 学生 ---------------------
def load_students(path="uploads/students.csv", mode=None):
    # ---- ファイルが無い／空なら「列だけある空 DataFrame」を返す ----
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["student_id", "department_name"])

    try:
        df = pd.read_csv(path, encoding="utf-8")
    except (FileNotFoundError, EmptyDataError):
        return pd.DataFrame(columns=["student_id", "department_name"])

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
    # --- 希望列を抽出（“第一希望”などを含む列） ---
    pref_cols = [c for c in df.columns if re.match(r"第?[一二三四]希望", c)]

    # ✅ 中身が実質 “空” の希望列は除外
    def is_blank_series(s: pd.Series) -> bool:
        """NaN / 空文字 / 全半角空白しか無い列なら True"""
        return s.fillna("").astype(str).str.strip().eq("").all()
    
    pref_cols = [c for c in pref_cols if not is_blank_series(df[c])]

    # モード判定
    mode = 4 if len(pref_cols) >= 4 else 3
    print("pref_cols =", pref_cols)
    print("mode =", mode)
    return df_pref, mode, student_dept_map

# --------------------- 企業 ---------------------
def load_companies(path="uploads/companies.csv"):
    # ---- ファイルが無い／空なら「列だけある空 DataFrame」を返す ----
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["company_name", "department_id"])

    try:
        df = pd.read_csv(path, encoding="utf-8")
    except (FileNotFoundError, EmptyDataError):
        return pd.DataFrame(columns=["company_name", "department_id"])
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