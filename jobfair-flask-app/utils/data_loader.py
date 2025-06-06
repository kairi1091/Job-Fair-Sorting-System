import pandas as pd
import re

def load_students(path="data/students.csv", mode=None):
    df = pd.read_csv(path)

    required_cols = ["学籍番号", "希望事業所1", "希望事業所2", "希望事業所3"]
    if any(col not in df.columns for col in required_cols):
        raise ValueError("CSVに必要な列が不足しています（希望事業所1〜3が必要）")

    df = df.rename(columns={
        "学籍番号": "student_id",
        "希望事業所1": "company_1",
        "希望事業所2": "company_2",
        "希望事業所3": "company_3",
        "希望事業所4": "company_4",
    })

    for col in ["company_1", "company_2", "company_3", "company_4"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(str).str.strip()     # ←★ 空白除去をここで

    if mode is None:
        if df["company_4"].notna().any() and df["company_4"].astype(str).str.strip().ne("").any():
            mode = 2
        else:
            mode = 1

    max_rank = 4 if mode == 2 else 3

    pref_list = []
    for _, row in df.iterrows():
        for rank in range(1, max_rank + 1):
            company = row.get(f"company_{rank}")
            if pd.notna(company) and str(company).strip():
                pref_list.append({
                    "student_id": str(row["student_id"]).strip(),
                    "company_name": str(company).strip(),
                    "rank": rank
                })

    df_preference = pd.DataFrame(pref_list)
    return df_preference, mode


def load_companies(path):
    df = pd.read_csv(path)
    df["企業名"] = df["企業名"].str.strip()
    df = df[df["企業名"].notna()]
    df = df[df["企業名"] != ""]
    df = df.rename(columns={"業種": "department_id"})
    return df

def get_department_id(student_id):
    match = re.search(r"[A-Z]", student_id)
    return match.group() if match else None
