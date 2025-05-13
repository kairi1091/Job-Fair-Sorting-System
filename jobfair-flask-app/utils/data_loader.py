import pandas as pd
import re

def load_students(path):
    df = pd.read_csv(path)
    df = df.rename(columns={
        "学籍番号": "student_id",
        "希望事業所1": "company_1",
        "希望事業所2": "company_2",
        "希望事業所3": "company_3"
    })

    pref_list = []
    for _, row in df.iterrows():
        for rank in range(1, 4):
            company = row.get(f"company_{rank}")
            if pd.notna(company):
                pref_list.append({
                    "student_id": row["student_id"],
                    "company_name": company.strip(),
                    "rank": rank
                })

    return pd.DataFrame(pref_list)

def load_companies(path):
    df = pd.read_csv(path)
    df = df[df["企業名"].notna()]
    df = df[df["企業名"].str.strip() != ""]
    df["企業名"] = df["企業名"].str.strip()
    df = df.rename(columns={"業種": "department_id"})
    return df

def get_department_id(student_id):
    match = re.search(r"[A-Z]", student_id)
    return match.group() if match else None
