import re, unicodedata, pandas as pd

def _norm(text: str) -> str:
    """ 空白・改行など一切合切を取り除き、NFKC 正規化 """
    if pd.isna(text):
        return ""
    # ① Unicode 正規化（全角→半角・合字解除など）
    text = unicodedata.normalize("NFKC", str(text))
    # ② 改行・タブ・ゼロ幅スペースなど全ホワイトスペースを1つの空白に
    text = re.sub(r"\s+", " ", text)
    # ③ 先頭末尾の空白を削除
    return text.strip()


def build_diagnosis(
    df_pref,
    student_schedule: dict,        # {sid: [slot0, slot1, …]}
    df_company: pd.DataFrame,      # 企業 DataFrame（dept 列が必要）
    student_dept_map: dict
):
    """cross_pref / cross_assign を検出"""
    # --- 企業 → 学科（企業名＋学科でユニークに） ---
    comp2dept = {
        (_norm(row["company_name"]), _norm(row["department_id"])): _norm(row["department_id"])
        for _, row in df_company.iterrows()
    }

    rows            = []
    cross_pref_list = []   # (sid, company)
    cross_asgn_list = []   # (sid, company)

    # ---------- ① 希望判定 ----------
    for _, r in df_pref.iterrows():
        sid   = r["student_id"]
        cname = _norm(r["company_name"])
        rank  = int(r["rank"])
        sdept = _norm(student_dept_map.get(sid, ""))

        key      = (cname, sdept)
        cdept    = comp2dept.get(key)       # None なら学科外
        is_cross = key not in comp2dept

        if is_cross:
            cross_pref_list.append((sid, r["company_name"]))  # 元の表記で保持

        rows.append({
            "student_id"   : sid,
            "student_dept" : sdept,
            "company"      : cname,
            "company_dept" : cdept,
            "rank"         : rank,
            "phase"        : "preference",
            "result"       : "cross_pref" if is_cross else "OK",
        })

    # ---------- ② 割当判定 ----------
    for sid, slots in student_schedule.items():
        sdept = _norm(student_dept_map.get(sid, ""))
        for slot_idx, cname_raw in enumerate(slots):
            if cname_raw is None:
                continue
            cname  = _norm(cname_raw)
            key      = (cname, sdept)
            cdept    = comp2dept.get(key)
            is_cross = key not in comp2dept
            if is_cross:
                cross_asgn_list.append((sid, cname_raw))      # 元の表記で保持

            rows.append({
                "student_id"   : sid,
                "student_dept" : sdept,
                "company"      : cname,
                "company_dept" : cdept,
                "slot"         : slot_idx,
                "phase"        : "assignment",
                "result"       : "cross_assign" if is_cross else "OK",
            })

    df_diag = pd.DataFrame(rows)
    return df_diag, cross_pref_list, cross_asgn_list
