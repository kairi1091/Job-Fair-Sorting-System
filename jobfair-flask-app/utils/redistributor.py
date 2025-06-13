def fill_remaining_gaps(student_schedule, company_capacity, max_slots):
    num_slots = len(next(iter(student_schedule.values())))
    filled = 0
    # ① 残キャパ slot を列挙
    gaps = [(c, s) for c, caps in company_capacity.items()
                        for s, cap in enumerate(caps) if cap > 0]
    for cname, slot in gaps:
        # ② 候補学生を探す
        for sid, slots in student_schedule.items():
            if sum(v is not None for v in slots) >= max_slots:
                continue
            if slots[slot] is not None or cname in slots:
                continue
            # ③ 連続になるか確認
            idx = [i for i,v in enumerate(slots) if v is not None] + [slot]
            if max(idx) - min(idx) + 1 != len(idx):      # 飛びコマなら NG
                continue
            # ④ 割当
            student_schedule[sid][slot] = cname
            company_capacity[cname][slot] -= 1
            filled += 1
            break
    print(f"✅ GAP 再配分で {filled} コマ補完")
