import random, math, statistics, csv, argparse

# ---------------------------
# Tunables
# ---------------------------
N_SIMS = 10_000
DICE_TO_TEST = [4, 6, 8, 10, 12, 20]  # warrior damage dice for 1v1
RANDOM_SEED = 42

# Core stats
WARRIOR = dict(HP=71, AC=16, ATK_MOD=3, DMG_MOD=3)

#Healer stats
#Cleric - HP: 63, AC: 12, ATK_MOD: 2, DMG_MOD: 2, DMG_DIE: 6
HEALER  = dict(HP=63, AC=12, ATK_MOD=2, DMG_MOD=2, DMG_DIE=6)

# 5e-like spell slots for a level 10 full caster
HEALER_SLOTS_L10 = {1: 4, 2: 3, 3: 2, 4: 2, 5: 1}

# Spells and healing amounts
# cure_wounds:     1d8 + mod (+1d8 per slot above 1st)
# healing_word:    1d4 + mod (+1d4 per slot above 1st)
# mass_healing_word (>=3rd): 1d4 + mod (+1d4 per slot above 3rd), heals both allies here
def heal_amount(spell: str, slot_level: int, mod: int) -> int:
    if spell == "cure_wounds":
        dice = 1 + max(0, slot_level - 1)
        return sum(roll(8) for _ in range(dice)) + mod
    elif spell == "healing_word":
        dice = 1 + max(0, slot_level - 1)
        return sum(roll(4) for _ in range(dice)) + mod
    elif spell == "mass_healing_word":  # requires slot >= 3
        dice = 1 + max(0, slot_level - 3)
        return sum(roll(4) for _ in range(dice)) + mod
    return 0

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

MONSTERS = {
    "CLOAKER": CLOAKER,
    "BLUE_SLAAD": BLUE_SLAAD,
    "GIANT_APE": GIANT_APE,
    "YOUNG_BLUE_DRAGON": YOUNG_BLUE_DRAGON,
    "ABERRANT_SCREECHER": ABERRANT_SCREECHER,
    "DOOM_MARAUDER": DOOM_MARAUDER,
}

def get_monster(name: str):
    key = name.strip().upper().replace(" ", "_")
    if key in MONSTERS:
        return MONSTERS[key], key
    # Alias rápidos
    aliases = {
        "BLUE": "BLUE_SLAAD",
        "SLAAD": "BLUE_SLAAD",
        "APE": "GIANT_APE",
        "DRAGON": "YOUNG_BLUE_DRAGON",
        "SCREECHER": "ABERRANT_SCREECHER",
        "DOOM": "DOOM_MARAUDER",
    }
    if key in aliases and aliases[key] in MONSTERS:
        return MONSTERS[aliases[key]], aliases[key]
    # Fallback
    return MONSTERS["CLOAKER"], "CLOAKER"

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
    party_first = (order[0] == "warrior") # <- clave unificada

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
        party_first = party_first,  # <- clave unificada
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
    party_first = [r["party_first"] for r in results]
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
        "P(win | party first)": conditional_prob(wins, party_first),
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
    
    
    slots = dict(HEALER_SLOTS_L10)
    SPELL_MOD = HEALER["DMG_MOD"]

    # Iniciativa a 3 bandas
    order = initiative_order(["warrior","healer","monster"])
    party_first = (min(order.index("warrior"), order.index("healer")) < order.index("monster"))

    # Flags para condiciones (del GUERRERO y del 1er ataque del MONSTRUO)
    first_warrior_attack_done = False
    first_monster_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False
    received_crit_first_turn = False

    # Racha de críticos del guerrero
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    t = 0
    while w_hp > 0 and h_hp > 0 and m_hp > 0:
        actor = order[t % 3]
        if actor == "warrior":
            r, crit, miss = roll_attack()
            if not first_warrior_attack_done:
                first_attack_was_crit = crit
                first_attack_was_miss = miss
                first_warrior_attack_done = True
            if not miss:
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

        elif actor == "healer":
            # si ambos están a full HP, el healer ataca al monstruo
            if (w_hp >= max_w) and (h_hp >= max_h):
                r, crit, miss = roll_attack()
                if not miss:
                    hit = crit or ((r + HEALER["ATK_MOD"]) >= monster["AC"])
                    if hit:
                        m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
            else:
                # Decide spell + slot based on injuries & availability
                both_injured = (w_hp < max_w) and (h_hp < max_h)
                someone_low  = (w_hp < max_w*0.5) or (h_hp < max_h*0.5)

                chosen = None  # (spell_name, slot_level)
                # Prefer Mass Healing Word if both are hurt and we have >=3rd slot
                if both_injured:
                    avail = max([lvl for lvl,cnt in slots.items() if cnt>0 and lvl>=3], default=0)
                    if avail >= 3:
                        chosen = ("mass_healing_word", avail)

                # If someone is low, use best Cure Wounds available
                if (chosen is None) and someone_low:
                    avail = max([lvl for lvl,cnt in slots.items() if cnt>0], default=0)
                    if avail >= 1:
                        chosen = ("cure_wounds", avail)

                # Otherwise, top up lightly with Healing Word if we have low slots
                if (chosen is None) and ((w_hp < max_w) or (h_hp < max_h)):
                    avail = max([lvl for lvl,cnt in slots.items() if cnt>0 and lvl<=2], default=0)
                    if avail >= 1:
                        chosen = ("healing_word", avail)

                if chosen is None:
                    # No slots or no need -> attack
                    r, crit, miss = roll_attack()
                    if not miss:
                        hit = crit or ((r + HEALER["ATK_MOD"]) >= monster["AC"])
                        if hit:
                            m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
                else:
                    spell, lvl = chosen
                    if spell == "mass_healing_word":
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        w_hp = min(max_w, w_hp + heal)
                        h_hp = min(max_h, h_hp + heal)
                    elif spell in ("cure_wounds", "healing_word"):
                        target_is_w = (w_hp <= h_hp)
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        if target_is_w: w_hp = min(max_w, w_hp + heal)
                        else:           h_hp = min(max_h, h_hp + heal)
                    slots[lvl] -= 1

        else:  # monster
            target_is_h = (h_hp <= w_hp)  # ties -> healer
            r, crit, miss = roll_attack()
            if not first_monster_attack_done:
                if crit: received_crit_first_turn = True
                first_monster_attack_done = True
            if not miss:
                target_ac = HEALER["AC"] if target_is_h else WARRIOR["AC"]
                hit = crit or ((r + monster["ATK_MOD"]) >= target_ac)
                if hit:
                    d = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                    if target_is_h: h_hp -= d
                    else:           w_hp -= d
        t += 1

    # Cierra racha si quedó abierta
    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    party_won = (m_hp <= 0) and (w_hp > 0 or h_hp > 0)
    return dict(
        warrior_won = party_won,
        party_first = party_first,                  # <- clave unificada (aliado antes que monstruo)
        first_attack_crit = first_attack_was_crit,  # 1er ATAQUE DEL GUERRERO fue crítico
        first_attack_miss = first_attack_was_miss,  # 1er ATAQUE DEL GUERRERO falló
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )
    
def simulate_many_with_healer(w_die, monster=GIANT_APE):
    results = [simulate_battle_with_healer(w_die, monster) for _ in range(N_SIMS)]
    wins = [r["warrior_won"] for r in results]
    base = sum(wins) / N_SIMS
    party_first = [r["party_first"] for r in results]
    first_crit = [r["first_attack_crit"] for r in results]
    first_miss = [r["first_attack_miss"] for r in results]
    got_crit_first = [r["received_crit_first_turn"] for r in results]

    all_streaks = []
    for r in results:
        all_streaks.extend(s for s in r["crit_streaks"] if s >= 0)
    pos = [s for s in all_streaks if s > 0]
    avg_streak = statistics.mean(pos) if pos else 0.0
    min_streak = min(pos) if pos else 0
    max_streak = max(pos) if pos else 0

    return {
        "warrior_die": f"d{w_die}",
        "baseline_P(win)": base,
        "P(win | party first)": conditional_prob(wins, party_first),
        "P(win | first attack crit)": conditional_prob(wins, first_crit),
        "ΔP(win) if first attack missed": conditional_prob(wins, first_miss) - base,
        "ΔP(win) if received crit on monster first turn": conditional_prob(wins, got_crit_first) - base,
        "crit_streak_min": min_streak,
        "crit_streak_max": max_streak,
        "crit_streak_avg>0": avg_streak,
    }

# ---------------------------
# Main
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(description="DnD battle simulator (1v1 vs healer comparison)")
    p.add_argument("--monster", type=str, default="CLOAKER",
                   help="Elige monstruo: CLOAKER | BLUE_SLAAD | GIANT_APE | YOUNG_BLUE_DRAGON | ABERRANT_SCREECHER | DOOM_MARAUDER")
    return p.parse_args()

def main():
    random.seed(RANDOM_SEED)
    args = parse_args()
    monster, mname = get_monster(args.monster)

    # A) 1v1 summaries per damage die
    rows_1v1 = [simulate_many_1v1(d, monster=monster) for d in DICE_TO_TEST]
    with open("dnd_1v1_summaries.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_1v1[0].keys()))
        w.writeheader()
        for r in rows_1v1:
            for k in list(r.keys()):
                if isinstance(r[k], float):
                    r[k] = round(r[k], 4)
            w.writerow(r)

    # B) Healer scenario (mismos campos/condicionales)
    rows_healer = [simulate_many_with_healer(d, monster=monster) for d in DICE_TO_TEST]
    with open("dnd_healer_summaries.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_healer[0].keys()))
        w.writeheader()
        for r in rows_healer:
            for k in list(r.keys()):
                if isinstance(r[k], float):
                    r[k] = round(r[k], 4)
            w.writerow(r)

    # Console preview
    print(f"Monster selected: {mname}")
    print("---- 1v1 summaries ----")
    for r in rows_1v1: print(r)
    print("\n---- Healer summaries ----")
    for r in rows_healer: print(r)
    print("\nFiles written: dnd_1v1_summaries.csv, dnd_healer_summaries.csv")

if __name__ == "__main__":
    main()