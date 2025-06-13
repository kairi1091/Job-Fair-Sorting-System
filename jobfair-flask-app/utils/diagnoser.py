# utils/diagnoser.py
import pandas as pd

def build_diagnosis(
    df_pref,
    student_schedule: dict,        # {sid: [slot0, slot1, …]}
    df_company: pd.DataFrame,      # 企業 DataFrame（dept 列が必要）
):
    """
    - cross_pref  : 学生が『希望として書いた』企業が学科外
    - cross_assign: 『実際に割り当てられた』企業が学科外
    どちらも検出して返す
    """
    # 企業 → 学科
    comp2dept = df_company.set_index("企業名")["department_id"].to_dict()

    rows            = []
    cross_pref_list = []   # (sid, company)
    cross_asgn_list = []   # (sid, company)

    # ── ① 希望（rank 別）を回して cross_pref を判定 ──
    for _, r in df_pref.iterrows():
        sid   = r["student_id"]
        cname = r["company_name"]
        rank  = int(r["rank"])
        sdept = get_department_id(sid)
        cdept = comp2dept.get(cname)

        if cdept is None or cdept != sdept:
            cross_pref_list.append((sid, cname))

        rows.append({
            "student_id"        : sid,
            "student_dept"      : sdept,
            "company"           : cname,
            "company_dept"      : cdept,
            "rank"              : rank,
            "phase"             : "preference",
            "result"            : "cross_pref" if (cdept != sdept) else "OK",
        })

    # ── ② 割り当てを回して cross_assign を判定 ──
    for sid, slots in student_schedule.items():
        sdept = get_department_id(sid)
        for slot_idx, cname in enumerate(slots):
            if cname is None:
                continue
            cdept = comp2dept.get(cname)
            is_cross = cdept is None or cdept != sdept
            if is_cross:
                cross_asgn_list.append((sid, cname))

            rows.append({
                "student_id"        : sid,
                "student_dept"      : sdept,
                "company"           : cname,
                "company_dept"      : cdept,
                "slot"              : slot_idx,
                "phase"             : "assignment",
                "result"            : "cross_assign" if is_cross else "OK",
            })

    df_diag = pd.DataFrame(rows)
    return df_diag, cross_pref_list, cross_asgn_list
