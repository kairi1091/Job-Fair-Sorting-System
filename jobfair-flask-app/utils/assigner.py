import random

def assign_preferences(df_ranked, point, student_schedule, student_score,
                       student_assigned_companies, company_capacity,
                       num_slots, mode, phase_label="", enable_fair_draw=True):

    for company in df_ranked["company_name"].unique():
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


from utils.data_loader import get_department_id

def fill_with_industry_match(student_schedule, student_assigned_companies,
                              company_capacity, df_company, num_slots):
    filled = 0
    for sid, slots in student_schedule.items():
        dept = get_department_id(sid)
        if dept is None:
            continue

        for slot_idx, assigned in enumerate(slots):
            if assigned is not None:
                continue  # すでに割当済みならスキップ

            matched_companies = df_company[df_company["department_id"] == dept]["企業名"].tolist()
            candidates = []
            for company in matched_companies:
                if company in student_schedule[sid]:
                    continue  # 同一企業は重複禁止
                if company_capacity.get(company, [0]*num_slots)[slot_idx] > 0:
                    candidates.append(company)

            if not candidates:
                continue

            selected_company = random.choice(candidates)
            student_schedule[sid][slot_idx] = selected_company
            student_assigned_companies[sid].add(selected_company)
            company_capacity[selected_company][slot_idx] -= 1
            filled += 1
    print(f"✅ STEP 4: 補完済みスロット数 = {filled}")
    return filled

def fill_with_random(student_schedule, student_assigned_companies,
                     company_capacity, num_slots):
    filled = 0
    for sid, slots in student_schedule.items():
        for slot_idx, assigned in enumerate(slots):
            if assigned is not None:
                continue

            # 空いてるキャパのある企業で、かつその学生に割当済みでない企業
            candidates = [
                company for company, caps in company_capacity.items()
                if caps[slot_idx] > 0 and company not in student_schedule[sid]
            ]

            if not candidates:
                continue

            selected_company = random.choice(candidates)
            student_schedule[sid][slot_idx] = selected_company
            student_assigned_companies[sid].add(selected_company)
            company_capacity[selected_company][slot_idx] -= 1
            filled += 1
    print(f"✅ STEP 5: ランダム補完済みスロット数 = {filled}")
    return filled
