import random, math, statistics, csv

# ---------------------------
# Tunables
# ---------------------------
N_SIMS = 10_000
DICE_TO_TEST = [4, 6, 8, 10, 12, 20]  # warrior damage dice for 1v1
RANDOM_SEED = 42

# Core stats
WARRIOR = dict(HP=71, AC=16, ATK_MOD=3, DMG_MOD=3)
HEALER  = dict(HP=63, AC=12, ATK_MOD=2, DMG_MOD=2, DMG_DIE=6)

#lvl 10 party members for full party scenario
#Fighter - HP: 100, AC: 18, ATK_MOD: 5, DMG_MOD: 4, DMG_DIE: 10
#Rogue - HP: 80, AC: 16, ATK_MOD: 6, DMG_MOD: 3, DMG_DIE: 8
#Wizard - HP: 60, AC: 12, ATK_MOD: 4, DMG_MOD: 5, DMG_DIE: 6
FIGHTER = dict(HP=100, AC=18, ATK_MOD=5, DMG_MOD=4, DMG_DIE=10)
ROGUE   = dict(HP=80, AC=16, ATK_MOD=6, DMG_MOD=3, DMG_DIE=8)
WIZARD  = dict(HP=60, AC=12, ATK_MOD=4, DMG_MOD=5, DMG_DIE=6)

#MONSTERS!
#Cloaker - HP: 78, AC: 14, ATK_MOD: 4, DMG_MOD: 2, DMG_DIE: 8
#Blue Slaad - HP: 104, AC: 17, ATK_MOD: 5, DMG_MOD: 3, DMG_DIE: 8
#Giant Ape - HP: 157, AC: 12, ATK_MOD: 7, DMG_MOD: 4, DMG_DIE: 12
#Young Blue Dragon - HP: 152, AC: 18, ATK_MOD: 7, DMG_MOD: 4, DMG_DIE: 10
#Aberrant Screecher(homebrew) - HP: 140, AC: 20, ATK_MOD: 8, DMG_MOD: 0, DMG_DIE: 6
#Doom Marauder(homebrew) - HP: 180, AC: 17, ATK_MOD: 3, DMG_MOD: 3, DMG_DIE: 12
CLOAKER = dict(HP=78, AC=14, ATK_MOD=4, DMG_MOD=2, DMG_DIE=8)
BLUE_SLAAD = dict(HP=104, AC=17, ATK_MOD=5, DMG_MOD=3, DMG_DIE=8)
GIANT_APE = dict(HP=157, AC=12, ATK_MOD=7, DMG_MOD=4, DMG_DIE=12)
YOUNG_BLUE_DRAGON = dict(HP=152, AC=18, ATK_MOD=7, DMG_MOD=4, DMG_DIE=10)
ABERRANT_SCREECHER = dict(HP=140, AC=20, ATK_MOD=8, DMG_MOD=0, DMG_DIE=6)
DOOM_MARAUDER = dict(HP=180, AC=17, ATK_MOD=3, DMG_MOD=3, DMG_DIE=12)

# ---------------------------
# Dice helpers
# ---------------------------
def roll(d): return random.randint(1, d)

def roll_attack():
    r = roll(20)
    return r, (r == 20), (r == 1)  # value, is_crit, is_crit_miss

def dmg(die, mod, crit=False):
    return (roll(die) + roll(die) + mod) if crit else (roll(die) + mod)

# ---------------------------
# Initiative
# ---------------------------
def initiative_order(names):
    scores = {n: roll(20) for n in names}
    while True:
        groups = {}
        for n, s in scores.items():
            groups.setdefault(s, []).append(n)
        ties = [g for g in groups.values() if len(g) > 1]
        if not ties: break
        for g in ties:
            for n in g:
                scores[n] = roll(20)
    return sorted(names, key=lambda n: scores[n], reverse=True)

# ---------------------------
# 1v1 battle
# ---------------------------
def simulate_battle_1v1(w_die, monster=GIANT_APE):
    w_hp = WARRIOR["HP"]
    m_hp = monster["HP"]
    order = initiative_order(["warrior", "monster"])
    warrior_first = (order[0] == "warrior")

    first_warrior_attack_done = False
    first_monster_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False
    received_crit_first_turn = False

    # crit streak tracking (warrior)
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    turn = 0
    while w_hp > 0 and m_hp > 0:
        actor = order[turn % 2]
        if actor == "warrior":
            r, crit, miss = roll_attack()
            if not first_warrior_attack_done:
                first_attack_was_crit = crit
                first_attack_was_miss = miss
                first_warrior_attack_done = True
            if miss:
                if cur_streak > 0:
                    all_streaks.append(cur_streak)
                    max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                    cur_streak = 0
            else:
                hit = crit or ((r + WARRIOR["ATK_MOD"]) >= monster["AC"])
                if hit:
                    if crit:
                        cur_streak += 1
                    else:
                        if cur_streak > 0:
                            all_streaks.append(cur_streak)
                            max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                            cur_streak = 0
                    m_hp -= dmg(w_die, WARRIOR["DMG_MOD"], crit)
                else:
                    if cur_streak > 0:
                        all_streaks.append(cur_streak)
                        max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                        cur_streak = 0
        else:
            r, crit, miss = roll_attack()
            if not first_monster_attack_done:
                if crit: received_crit_first_turn = True
                first_monster_attack_done = True
            if not miss:
                hit = crit or ((r + monster["ATK_MOD"]) >= WARRIOR["AC"])
                if hit:
                    w_hp -= dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
        turn += 1

    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    return dict(
        warrior_won = (w_hp > 0 and m_hp <= 0),
        warrior_first = warrior_first,
        first_attack_crit = first_attack_was_crit,
        first_attack_miss = first_attack_was_miss,
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )

def conditional_prob(wins, cond):
    num = sum(1 for w,c in zip(wins,cond) if c and w)
    den = sum(1 for c in cond if c)
    return (num/den) if den else float("nan")

def simulate_many_1v1(w_die , monster=GIANT_APE):
    results = [simulate_battle_1v1(w_die, monster) for _ in range(N_SIMS)]
    wins = [r["warrior_won"] for r in results]
    base = sum(wins) / N_SIMS
    went_first = [r["warrior_first"] for r in results]
    first_crit = [r["first_attack_crit"] for r in results]
    first_miss = [r["first_attack_miss"] for r in results]
    got_crit_first = [r["received_crit_first_turn"] for r in results]

    all_streaks = []
    for r in results: all_streaks.extend(s for s in r["crit_streaks"] if s >= 0)
    pos = [s for s in all_streaks if s > 0]
    avg_streak = statistics.mean(pos) if pos else 0.0
    min_streak = min(pos) if pos else 0
    max_streak = max(pos) if pos else 0

    return {
        "warrior_die": f"d{w_die}",
        "baseline_P(win)": base,
        "P(win | warrior first)": conditional_prob(wins, went_first),
        "P(win | first attack crit)": conditional_prob(wins, first_crit),
        "ΔP(win) if first attack missed": conditional_prob(wins, first_miss) - base,
        "ΔP(win) if received crit on monster first turn": conditional_prob(wins, got_crit_first) - base,
        "crit_streak_min": min_streak,
        "crit_streak_max": max_streak,
        "crit_streak_avg>0": avg_streak,
    }

# ---------------------------
# Healer scenario
# ---------------------------
def simulate_battle_with_healer(w_die=10, monster=GIANT_APE):
    w_hp = WARRIOR["HP"]; h_hp = HEALER["HP"]
    m_hp = monster["HP"]
    max_w = WARRIOR["HP"]; max_h = HEALER["HP"]

    order = initiative_order(["warrior","healer","monster"])
    t = 0
    while w_hp > 0 and h_hp > 0 and m_hp > 0:
        actor = order[t % 3]
        if actor == "warrior":
            r, crit, miss = roll_attack()
            if not miss:
                hit = crit or ((r + WARRIOR["ATK_MOD"]) >= monster["AC"])
                if hit:
                    m_hp -= dmg(w_die, WARRIOR["DMG_MOD"], crit)

        elif actor == "healer":
            # si ambos están a full HP, el healer ataca al monstruo
            if (w_hp >= max_w) and (h_hp >= max_h):
                r, crit, miss = roll_attack()
                if not miss:
                    hit = crit or ((r + HEALER["ATK_MOD"]) >= monster["AC"])
                    if hit:
                        m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
            else:
                # Lógica de curación: cura a quien tenga menos HP (empate -> guerrero)
                target_is_w = (w_hp <= h_hp)
                r = roll(20)
                if r == 20:
                    if target_is_w: w_hp = max_w
                    else:           h_hp = max_h
                elif r == 1:
                    if target_is_w: w_hp -= 1
                    else:           h_hp -= 1
                else:
                    #healer lvl 10: 2d8 + 5 HP
                    heal1 = roll(8)
                    heal2 = roll(8)
                    if target_is_w: w_hp = min(max_w, w_hp + heal1 + heal2 + 5)
                    else:           h_hp = min(max_h, h_hp + heal1 + heal2 + 5)

        else:  # monster
            target_is_h = (h_hp <= w_hp)  # ties -> healer
            r, crit, miss = roll_attack()
            if not miss:
                target_ac = HEALER["AC"] if target_is_h else WARRIOR["AC"]
                hit = crit or ((r + monster["ATK_MOD"]) >= target_ac)
                if hit:
                    d = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                    if target_is_h: h_hp -= d
                    else:           w_hp -= d
        t += 1

    return (m_hp <= 0) and (w_hp > 0 or h_hp > 0)

# ---------------------------
# Main
# ---------------------------
def main():
    random.seed(RANDOM_SEED)

    # A) 1v1 summaries per damage die
    rows = [simulate_many_1v1(d, monster=CLOAKER) for d in DICE_TO_TEST]

    # write CSV
    with open("dnd_1v1_summaries.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            # round probs for readability
            for k in list(r.keys()):
                if isinstance(r[k], float):
                    r[k] = round(r[k], 4)
            w.writerow(r)

    # B) Healer scenario (warrior d8)
    wins = sum(1 for _ in range(N_SIMS) if simulate_battle_with_healer(8))
    rate = round(wins / N_SIMS, 4)
    with open("dnd_healer_summary.csv","w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario","party_win_rate"])
        w.writerow(["Warrior(d8)+Healer vs Monster(HP sum)", rate])

    # Console preview
    print("---- 1v1 summaries ----")
    for r in rows: print(r)
    print("\nHealer scenario party_win_rate:", rate)
    print("\nFiles written: dnd_1v1_summaries.csv, dnd_healer_summary.csv")

if __name__ == "__main__":
    main()