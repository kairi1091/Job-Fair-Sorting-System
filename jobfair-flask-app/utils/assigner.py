import random
import math

def assign_preferences(df_ranked, point, student_schedule, student_score,
                       student_assigned_companies, company_capacity,valid_companies,
                       num_slots, mode, phase_label="", enable_fair_draw=True):

    for company in df_ranked["company_name"].unique():
        
        # ---------- 学科外はスキップ ----------
        if company not in valid_companies:
            continue
        
        candidates = df_ranked[df_ranked["company_name"] == company]["student_id"].tolist()

        for slot in range(num_slots):
            if mode == 1 and slot == 3:
                continue

            valid_candidates = []
            for sid in candidates:
                if student_schedule[sid][slot] is not None:
                    continue
                if company in student_schedule[sid]:
                    continue
                valid_candidates.append(sid)

            cap = company_capacity[company][slot]
            if cap == 0 or not valid_candidates:
                continue

            if len(valid_candidates) <= cap:
                selected = valid_candidates
            else:
                if enable_fair_draw:
                    sorted_candidates = sorted(valid_candidates, key=lambda x: student_score[x])
                    selected = random.sample(sorted_candidates[:cap * 2], k=cap)
                else:
                    selected = valid_candidates[:cap]

            for sid in selected:
                student_schedule[sid][slot] = company
                student_assigned_companies[sid].add(company)
                student_score[sid] += point
                company_capacity[company][slot] -= 1

    print(f"✅ {phase_label} の割当完了")


def run_pattern_a(df_preference, df_company, student_ids, dept_id, student_dept_map, cap, NUM_SLOTS=4):
    from .assigner import assign_preferences, fill_with_industry_match

    # --- Step 0: 初期化 ---
    student_schedule = {sid: [None] * NUM_SLOTS for sid in student_ids}
    student_score = {sid: 0 for sid in student_ids}
    student_assigned_companies = {sid: set() for sid in student_ids}
    company_capacity = {
        cname: [cap] * NUM_SLOTS for cname in df_company["company_name"]
    }

    # --- Step 1～3: 希望順に割当（第1～第4希望）---
    # --- 学科内企業リストを生成 ---
    valid_companies = df_company[
        df_company["department_id"] == dept_id
    ]["company_name"].tolist()
        
    for rank in range(1, 5):
        df_ranked = df_preference[df_preference["rank"] == rank]
        assign_preferences(
            df_ranked, point=(5 - rank),
            student_schedule=student_schedule,
            student_score=student_score,
            student_assigned_companies=student_assigned_companies,
            company_capacity=company_capacity,
            num_slots=NUM_SLOTS,
            mode=2,
            valid_companies=valid_companies,
            phase_label=f"第{rank}希望"
        )

    # --- Step 4: 学科マッチ補完 ---
    filled_step4 = fill_with_industry_match(
        student_schedule,                # ← schedule ではなく student_schedule
        student_assigned_companies,      # ← assigned ではなく student_assigned_companies
        company_capacity,                # ← capacity ではなく company_capacity
        df_company,                      # ← そのまま
        valid_companies,
        NUM_SLOTS,
        student_dept_map
    )


    filled_step5, reasons = fill_zero_slots(
        student_schedule, student_score, student_assigned_companies,
        company_capacity, df_company, df_preference,
        valid_companies, NUM_SLOTS
    )
 
    return (student_schedule, student_score,
            student_assigned_companies, company_capacity,
            filled_step4, filled_step5, reasons)
    

def run_pattern_b(df_preference, df_company, student_ids, student_dept_map, cap, num_slots=4):
    from .assigner import assign_preferences_b, adjust_continuous_slots, rescue_zero_visits, fill_with_industry_match, fill_zero_slots
    import math

    dept_id = student_dept_map.get(sid, "不明")
    valid_companies = df_company[df_company["department_id"] == dept_id]["company_name"].tolist()
    company_capacity = { cname: [cap] * num_slots for cname in valid_companies }

    total_capacity = len(valid_companies) * cap * num_slots
    max_slots = min(4, math.floor(total_capacity / len(student_ids)))

    # Step 1: 仮割当
    temp_schedule = {sid: [None] * num_slots for sid in student_ids}
    temp_assigned_companies = {sid: set() for sid in student_ids}
    temp_weights = {sid: [0] * num_slots for sid in student_ids}

    for rank in range(1, max_slots+1):
        df_ranked = df_preference[df_preference["rank"] == rank]
        assign_preferences_b(df_ranked, point=(5 - rank),
                              temp_schedule=temp_schedule,
                              temp_assigned_companies=temp_assigned_companies,
                              temp_weights=temp_weights,
                              num_slots=num_slots, max_slots=max_slots)

    # Step 2: 連続化 + キャパ反映
    student_schedule, student_assigned_companies = adjust_continuous_slots(
        temp_schedule, temp_weights, company_capacity, num_slots
    )

    # Step 3: 0訪問救済補完
    rescue_zero_visits(student_schedule, company_capacity, valid_companies, num_slots)

    # Step 4: 通常補完
    filled_step4 = fill_with_industry_match(
        student_schedule, student_assigned_companies,
        company_capacity, df_company, valid_companies, num_slots, student_dept_map
    )

    filled_step5, reasons = fill_zero_slots(
        student_schedule, {}, student_assigned_companies,
        company_capacity, df_company, df_preference,
        valid_companies, num_slots
    )

    return (student_schedule, {}, student_assigned_companies, company_capacity,
            filled_step4, filled_step5, reasons)
    

    
def assign_preferences_b(df_ranked, point, temp_schedule, temp_assigned_companies, temp_weights, num_slots, max_slots):
    for company in df_ranked["company_name"].unique():
        candidates = df_ranked[df_ranked["company_name"] == company]["student_id"].tolist()
        for sid in candidates:
            assigned_slots = [i for i, v in enumerate(temp_schedule[sid]) if v is not None]
            if len(assigned_slots) >= max_slots:
                continue
            for slot in range(num_slots):
                if temp_schedule[sid][slot] is None:
                    temp_schedule[sid][slot] = company
                    temp_assigned_companies[sid].add(company)
                    temp_weights[sid][slot] = point  # ここが追加
                    break


def adjust_continuous_slots(temp_schedule, temp_weights, company_capacity, num_slots):
    student_schedule = {}
    student_assigned_companies = {}

    for sid, slots in temp_schedule.items():
        assigned = [i for i, v in enumerate(slots) if v is not None]
        if not assigned:
            student_schedule[sid] = [None] * num_slots
            student_assigned_companies[sid] = set()
            continue

        min_slot = min(assigned)
        length = len(assigned)

        # スコア（希望反映度）順に整列して優先割当
        success = False
        for start in range(max(0, min_slot - (length - 1)), min_slot+1):
            trial = list(range(start, start+length))
            if max(trial) >= num_slots:
                continue
            score = sum(temp_weights[sid][i] for i in assigned)
            # 全てキャパOKなら採用
            if all(company_capacity[slots[i]][trial[j]] > 0 for j, i in enumerate(assigned)):
                for j, i in enumerate(assigned):
                    company_capacity[slots[i]][trial[j]] -= 1
                student_schedule[sid] = [None] * num_slots
                student_assigned_companies[sid] = set()
                for j, i in enumerate(assigned):
                    student_schedule[sid][trial[j]] = slots[i]
                    student_assigned_companies[sid].add(slots[i])
                success = True
                break

        if not success:
            student_schedule[sid] = [None] * num_slots
            student_assigned_companies[sid] = set()

    return student_schedule, student_assigned_companies

def rescue_zero_visits(student_schedule, company_capacity, valid_companies, num_slots):
    filled = 0
    for sid, slots in student_schedule.items():
        if all(s is None for s in slots):
            # 空いてるスロットを優先検索
            for slot in range(num_slots):
                candidates = [
                    cname for cname in valid_companies
                    if company_capacity[cname][slot] > 0
                ]
                if candidates:
                    selected = random.choice(candidates)
                    student_schedule[sid][slot] = selected
                    company_capacity[selected][slot] -= 1
                    filled += 1
                    break
    print(f"✅ 0訪問救済補完 {filled}件")
    return filled

# ---------------------共通部品---------------------
def fill_with_industry_match(student_schedule, student_assigned_companies,
                              company_capacity, df_company,valid_companies, num_slots, student_dept_map):
    filled = 0
    for sid, slots in student_schedule.items():
        dept = student_dept_map[sid]    # 呼び出し側で辞書を渡す
        if dept is None:
            continue

        for slot_idx, assigned in enumerate(slots):
            if assigned is not None:
                continue  # すでに割当済みならスキップ

            matched_companies = df_company[df_company["department_id"] == dept]["company_name"].tolist()
            candidates = []
            for company in matched_companies:
                if company not in valid_companies:      # ★ ここでまず学科外を排除
                    continue
                if company in student_schedule[sid]:
                    continue  # 同一企業は重複禁止
                if company_capacity.get(company, [0]*num_slots)[slot_idx] > 0:
                    candidates.append(company)

            if not candidates:
                continue
            
         # 学科外はスキップ

            selected_company = random.choice(candidates)
            student_schedule[sid][slot_idx] = selected_company
            student_assigned_companies[sid].add(selected_company)
            company_capacity[selected_company][slot_idx] -= 1
            filled += 1
    print(f"✅ STEP 4: 補完済みスロット数 = {filled}")
    return filled
    
def fill_zero_slots(student_schedule, student_score, student_assigned_companies,
                    company_capacity, df_company, df_preference,
                    valid_companies,          # ★ 追加
                    num_slots=4):
    """
    「0人ブース」を学科内企業だけで埋める
    """
    filled, reasons = 0, {}

    # --- 対象スロットを列挙（企業×slot で割当数 = 0 のもの） ---
    zero_slots = [
        (cname, slot)
        for cname, caps in company_capacity.items()
        for slot, cap in enumerate(caps)
        if cap > 0 and cname in valid_companies               # ★ ここで学科外を除外
    ]

    if not zero_slots:
        print("✅ STEP 5: 0人スロットはありませんでした。")
        return 0, {}

    # --- 希望辞退者（希望なし）一覧作成 ---
    preference_by_student = df_preference.groupby("student_id")["company_name"].apply(set).to_dict()

    # スロットを埋めていく
    for cname, slot in zero_slots:
        
        if cname not in company_capacity:   # company_capacity は学科内だけ
            continue
        # --- 希望なし学生から探す ---
        candidates = []
        for sid, slots in student_schedule.items():
            if slots[slot] is not None:
                continue  # すでに何か入ってる

            if cname in slots:
                continue  # 同一企業は割当済み

            prefs = preference_by_student.get(sid, set())
            if not prefs:
                candidates.append(sid)

        # --- 希望なし学生から割当 ---
        if candidates:
            sid = random.choice(candidates)
            student_schedule[sid][slot] = cname
            student_assigned_companies[sid].add(cname)
            reasons.setdefault(sid, {})[slot] = "希望未入力のため上書き補完"
            filled += 1
            continue

        # --- 希望反映済み学生から割当（スコア順）---
        sorted_sids = sorted(student_score.items(), key=lambda x: -x[1])
        for sid, _ in sorted_sids:
            if student_schedule[sid][slot] is not None:
                continue
            if cname in student_schedule[sid]:
                continue
            student_schedule[sid][slot] = cname
            student_assigned_companies[sid].add(cname)
            reasons.setdefault(sid, {})[slot] = "希望が反映済みだったため補完上書き"
            filled += 1
            break

    print(f"✅ STEP 5: 0人スロット補完数 = {filled}")
    return filled, reasons
