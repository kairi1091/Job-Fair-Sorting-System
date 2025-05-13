import math

def is_real_company(val):
    """None / NaN / '自由訪問枠' を除いた企業名のみ対象"""
    return isinstance(val, str) and val != "自由訪問枠"

def check_schedule_violations(student_schedule, company_capacity=None):
    logs = []

    for sid, slots in student_schedule.items():
        # --- 重複企業チェック ---
        assigned = [v for v in slots if is_real_company(v)]
        duplicates = [v for v in set(assigned) if assigned.count(v) > 1]
        if duplicates:
            logs.append(f"⚠️ {sid}: 同一企業が複数スロットに割り当てられています → {assigned}")

        # --- 希望枠数の自動判定（3 or 4枠） ---
        slot_len = len(slots)
        is_mode3 = (slot_len == 4 and slots[3] == "自由訪問枠") or slot_len == 3
        required_slots = 3 if is_mode3 else 4

        # --- 希望枠に未割当があるかチェック ---
        has_empty = any(
            slots[i] is None or (isinstance(slots[i], float) and math.isnan(slots[i]))
            for i in range(required_slots)
        )
        if has_empty:
            logs.append(f"⚠️ {sid}: 希望枠（{required_slots}枠）がすべて埋まっていません → {slots}")

    return logs
