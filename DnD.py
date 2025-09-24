import random, statistics, csv, argparse
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')  # for headless servers
# ---------------------------
# Tunables
# ---------------------------
N_SIMS = 10_000
DICE_TO_TEST = [4, 6, 8, 10, 12, 20]  # warrior damage dice for 1v1
RANDOM_SEED = 42

# Warrior stats
WARRIOR = dict(HP=71, AC=16, ATK_MOD=3, DMG_MOD=3)

# --- Warrior abilities (simple 5e-flavored model) ---
WARRIOR_LEVEL = 10
WARRIOR_CON_MOD = 2  # not used now, but handy if you want
SECOND_WIND_THRESHOLD = 0.35   # heal when HP <= 35% of max
ACTION_SURGE_USES = 1
SUPERIORITY_DICE_N = 4         # Battlemaster dice count (lvl 10)
SUPERIORITY_DIE_D = 10         # d10 at lvl 10
POWER_ATTACK = dict(HIT_PENALTY=5, DMG_BONUS=10)  # GWM-like toggle (used when advantaged)

# Healer stats
HEALER  = dict(HP=63, AC=12, ATK_MOD=2, DMG_MOD=2, DMG_DIE=6)
HEALER_SLOTS_L10 = {1: 4, 2: 3, 3: 2, 4: 2, 5: 1}

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

# Rogue (lvl 10)
ROGUE   = dict(HP=80, AC=16, ATK_MOD=6, DMG_MOD=3, DMG_DIE=8)
SNEAK_ATTACK_DICE = 5
SNEAK_ATTACK_DIE  = 6
ROGUE_STEADY_AIM = True
ROGUE_UNCANNY_DODGE = True

# Wizard (lvl 10)
WIZARD  = dict(HP=60, AC=12, ATK_MOD=4, DMG_MOD=5, DMG_DIE=6)
WIZARD_SLOTS_L10 = {1: 4, 2: 3, 3: 2, 4: 2, 5: 1}
WIZARD_CANTRIP_DICE  = 2   # Fire Bolt at lvl 10 in this model
WIZARD_CANTRIP_DIE   = 10
WIZARD_SHIELD_ACTIVE = True

def wizard_spend_lowest_slot(slots: dict) -> int:
    for lvl in sorted(slots):
        if slots[lvl] > 0:
            slots[lvl] -= 1
            return lvl
    return 0

def wizard_highest_slot(slots: dict) -> int:
    highs = [lvl for lvl, cnt in slots.items() if cnt > 0]
    return max(highs) if highs else 0

def wizard_magic_missile_damage(slot_level: int) -> int:
    darts = slot_level + 2
    return sum(roll(4) + 1 for _ in range(darts))

def wizard_chromatic_orb_damage(slot_level: int, crit: bool) -> int:
    dice = slot_level + 2
    n = dice * (2 if crit else 1)
    return sum(roll(8) for _ in range(n))

def wizard_fire_bolt_damage(crit: bool) -> int:
    n = WIZARD_CANTRIP_DICE * (2 if crit else 1)
    return sum(roll(WIZARD_CANTRIP_DIE) for _ in range(n))

# MONSTERS
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

# Official-ish abstractions
CLOAKER.update(dict(ATTACKS=2))

BLUE_SLAAD.update(dict(
    ATTACKS=3,
    REGEN=10,
    SPELL_RESIST_AC_BONUS=2
))

GIANT_APE.update(dict(
    ATTACKS=2,
    CRIT_EXTRA_WEAPON_DICE=1
))

YOUNG_BLUE_DRAGON.update(dict(
    ATTACKS=2,
    BREATH=dict(N_DICE=8, DIE=10, RECHARGE=[5,6], SAVE_SUCCESS_P=0.5)
))

ABERRANT_SCREECHER.update(dict(
    ATTACKS=2,
    BREATH=dict(N_DICE=6, DIE=6, RECHARGE=[5,6], SAVE_SUCCESS_P=0.5),
    SPELL_RESIST_AC_BONUS=2
))

DOOM_MARAUDER.update(dict(
    ATK_MOD=3,
    ATTACKS=2,
    COUNTER_ON_MISS=True,
    COUNTER_DAMAGE_DIE=12,
    COUNTER_DAMAGE_MOD=5,
    SPELL_RESIST_AC_BONUS=3,
    AUTO_SPELL_RESIST_PCT=0.5,
    BREATH=dict(N_DICE=6, DIE=8, RECHARGE=[5,6], SAVE_SUCCESS_P=0.5),
    BREATH_CHARGES=2,
    WOLF=dict(TRIGGER_PCT=0.60, DURATION=4, DIE=10, MOD=3)
))

# ---------------------------
# Helpers
# ---------------------------
def roll(d): 
    return random.randint(1, d)

def roll_attack():
    r = roll(20)
    return r, (r == 20), (r == 1)

def roll_attack_adv(has_adv: bool):
    if not has_adv:
        r = roll(20)
        return r, (r == 20), (r == 1)
    r1, r2 = roll(20), roll(20)
    crit = (r1 == 20) or (r2 == 20)
    miss = (r1 == 1) and (r2 == 1)
    r = max(r1, r2)
    return r, crit, miss

def dmg(die, mod, crit=False):
    return (roll(die) + roll(die) + mod) if crit else (roll(die) + mod)

def monster_effective_ac(mon, is_spell_attack=False):
    ac = mon["AC"]
    if is_spell_attack:
        ac += mon.get("SPELL_RESIST_AC_BONUS", 0)
    return ac

def initiative_order(names):
    # Fast, single-pass tie-breaker using extra random keys
    keyed = {n: (roll(20), roll(20)) for n in names}
    return sorted(names, key=lambda n: keyed[n], reverse=True)

def end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle):
    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)
        cur_streak = 0
    return cur_streak, max_streak_in_battle

def try_breath(breath_cfg, breath_ready, breath_charges, targets_dict):
    """
    targets_dict: {tag: current_hp} only for alive targets.
    Returns: used_breath(bool), breath_ready, breath_charges, damage_per_tag(dict)
    - Implements per-target save for half.
    - If monster has >=2 charges and doubling would kill any target, expend 2.
    """
    if (not breath_cfg) or (not breath_ready) or (breath_charges <= 0) or (not targets_dict):
        return False, breath_ready, breath_charges, {}

    base = sum(roll(breath_cfg["DIE"]) for _ in range(breath_cfg["N_DICE"]))
    per = {}
    for tag, hp in targets_dict.items():
        d = base
        if random.random() < breath_cfg["SAVE_SUCCESS_P"]:
            d //= 2
        per[tag] = d

    # Double only if both charges exist AND doubling kills someone.
    use_two = (breath_charges >= 2) and any(2 * per[t] >= targets_dict[t] for t in per)
    applied = 2 if use_two else 1
    for t in per:
        per[t] *= applied

    breath_charges -= applied
    if breath_charges <= 0:
        breath_ready = False

    return True, breath_ready, breath_charges, per

def conditional_prob(wins, cond):
    num = sum(1 for w,c in zip(wins,cond) if c and w)
    den = sum(1 for c in cond if c)
    return (num/den) if den else float("nan")

def summarize_many(sim_fn, w_die, monster, n_sims=10_000):
    results = []
    for _ in range(n_sims):
        m = dict(monster)  # shallow copy for per-sim state
        results.append(sim_fn(w_die, m))

    wins = [r["warrior_won"] for r in results]
    base = sum(wins) / n_sims
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
        "wins": sum(wins),
        "losses": n_sims - sum(wins),
        "baseline_P(win)": base,
        "P(win | party first)": conditional_prob(wins, party_first),
        "P(win | first attack crit)": conditional_prob(wins, first_crit),
        "ΔP(win) if first attack missed": conditional_prob(wins, first_miss) - base,
        "ΔP(win) if received crit on monster first turn": conditional_prob(wins, got_crit_first) - base,
        "crit_streak_min": min_streak,
        "crit_streak_max": max_streak,
        "crit_streak_avg>0": avg_streak,
    }
    
def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            out = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}
            w.writerow(out)

# ---------------------------
# 1v1 battle
# ---------------------------
def simulate_battle_1v1(w_die, monster):
    w_hp = WARRIOR["HP"]
    m_hp = monster["HP"]
    max_w = WARRIOR["HP"]

    order = initiative_order(["warrior", "monster"])
    party_first = (order[0] == "warrior")

    # Warrior state
    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False

    # Monster state
    monster_max_hp = monster["HP"]
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)
    breath_max_charges = monster.get("BREATH_CHARGES", 1) if breath_cfg else 0
    breath_charges = breath_max_charges if breath_ready else 0

    # Marauder / wolf
    marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))
    wolf_cfg = monster.get("WOLF")
    wolf_rounds_left = 0
    wolf_summoned = False

    # Metrics flags
    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False
    first_monster_attack_done = False
    received_crit_first_turn = False

    # Crit streak tracking
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    turn = 0
    while w_hp > 0 and m_hp > 0:
        actor = order[turn % 2]
        if (turn % 2) == 0:
            marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))

        if actor == "warrior":
            # Second Wind (bonus-like)
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            attacks_this_turn = 1

            def do_one_attack(is_first_attack_of_warrior_turn):
                nonlocal m_hp, w_hp, cur_streak, max_streak_in_battle, all_streaks
                nonlocal sup_dice, warrior_adv_next, marauder_counter_ready
                nonlocal first_warrior_attack_done, first_attack_was_crit, first_attack_was_miss

                has_adv = warrior_adv_next
                warrior_adv_next = False

                use_power = has_adv
                atk_mod = WARRIOR["ATK_MOD"] - (POWER_ATTACK["HIT_PENALTY"] if use_power else 0)
                dmg_mod = WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if use_power else 0)

                r, crit, miss = roll_attack_adv(has_adv)
                final_hit = False
                if not miss:
                    raw_hit = crit or ((r + atk_mod) >= monster_effective_ac(monster))
                    if (not raw_hit) and (sup_dice > 0):
                        need = monster["AC"] - (r + atk_mod)
                        if 1 <= need <= SUPERIORITY_DIE_D:
                            sup_dice -= 1
                            add = roll(SUPERIORITY_DIE_D)
                            raw_hit = crit or ((r + add + atk_mod) >= monster_effective_ac(monster))
                    final_hit = raw_hit

                # Marauder counter on miss
                if (not final_hit) and monster.get("COUNTER_ON_MISS") and marauder_counter_ready and (m_hp > 0):
                    r2, c2, m2 = roll_attack()
                    if not m2 and (c2 or ((r2 + monster["ATK_MOD"]) >= WARRIOR["AC"])):
                        w_hp -= dmg(monster.get("COUNTER_DAMAGE_DIE", monster["DMG_DIE"]),
                                    monster.get("COUNTER_DAMAGE_MOD", monster["DMG_MOD"]), c2)
                    marauder_counter_ready = False

                if is_first_attack_of_warrior_turn and (not first_warrior_attack_done):
                    first_warrior_attack_done = True
                    first_attack_was_crit = crit
                    first_attack_was_miss = (not final_hit)

                if final_hit:
                    extra = 0
                    do_trip = (sup_dice > 0) and (not has_adv) and (m_hp > 0.5 * monster_max_hp)
                    if do_trip:
                        sup_dice -= 1
                        extra = roll(SUPERIORITY_DIE_D)
                        warrior_adv_next = True

                    if crit:
                        dmg_total = roll(w_die) + roll(w_die) + dmg_mod + extra
                        cur_streak += 1
                    else:
                        cur_streak, max_streak_in_battle = end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle)
                        dmg_total = roll(w_die) + dmg_mod + extra
                    m_hp -= dmg_total
                else:
                    cur_streak, max_streak_in_battle = end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle)

            # First attack
            do_one_attack(is_first_attack_of_warrior_turn=True)

            # Action Surge decision
            if (m_hp > 0) and (action_surge > 0):
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (m_hp <= 1.2 * expected_next):
                    action_surge -= 1
                    attacks_this_turn += 1

            if attacks_this_turn == 2 and m_hp > 0:
                do_one_attack(is_first_attack_of_warrior_turn=False)

        else:
            # --- Monster turn ---
            if monster.get("REGEN"):
                m_hp = min(monster_max_hp, m_hp + monster["REGEN"])

            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True
                    breath_charges = breath_max_charges

            used_breath, breath_ready, breath_charges, per = try_breath(
                breath_cfg, breath_ready, breath_charges, {"w": w_hp} if w_hp > 0 else {}
            )
            if used_breath and "w" in per:
                w_hp -= per["w"]

            # Wolf buddy
            if wolf_cfg and (not wolf_summoned) and (m_hp <= monster_max_hp * wolf_cfg["TRIGGER_PCT"]):
                wolf_summoned = True
                wolf_rounds_left = wolf_cfg["DURATION"]
            if wolf_cfg and wolf_rounds_left > 0 and w_hp > 0:
                w_hp -= (roll(wolf_cfg["DIE"]) + wolf_cfg["MOD"])
                wolf_rounds_left -= 1

            if not used_breath:
                for _ in range(monster.get("ATTACKS", 1)):
                    r, crit, miss = roll_attack()
                    if not miss:
                        hit = crit or ((r + monster["ATK_MOD"]) >= WARRIOR["AC"])
                        if hit:
                            d = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                            if crit and monster.get("CRIT_EXTRA_WEAPON_DICE", 0) > 0:
                                d += sum(roll(monster["DMG_DIE"]) for _ in range(monster["CRIT_EXTRA_WEAPON_DICE"]))
                            w_hp -= d
        turn += 1

    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    return dict(
        warrior_won = (w_hp > 0 and m_hp <= 0),
        party_first = party_first,
        first_attack_crit = first_attack_was_crit,
        first_attack_miss = first_attack_was_miss,
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )

# ---------------------------
# Healer scenario
# ---------------------------
def simulate_battle_with_healer(w_die=10, monster=GIANT_APE):
    w_hp = WARRIOR["HP"]; h_hp = HEALER["HP"]
    m_hp = monster["HP"]
    max_w = WARRIOR["HP"]; max_h = HEALER["HP"]

    slots = dict(HEALER_SLOTS_L10)
    SPELL_MOD = HEALER["DMG_MOD"]

    order = initiative_order(["warrior","healer","monster"])
    party_first = (min(order.index("warrior"), order.index("healer")) < order.index("monster"))

    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False

    monster_max_hp = monster["HP"]
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)
    breath_max_charges = monster.get("BREATH_CHARGES", 1) if breath_cfg else 0
    breath_charges = breath_max_charges if breath_ready else 0

    marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))
    wolf_cfg = monster.get("WOLF")
    wolf_rounds_left = 0
    wolf_summoned = False

    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False
    first_monster_attack_done = False
    received_crit_first_turn = False

    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    def marauder_counter_vs(attacker_is_healer: bool):
        nonlocal w_hp, h_hp, marauder_counter_ready
        if (not monster.get("COUNTER_ON_MISS")) or (not marauder_counter_ready) or (m_hp <= 0):
            return
        r2, c2, m2 = roll_attack()
        if m2:
            marauder_counter_ready = False
            return
        ac = HEALER["AC"] if attacker_is_healer else WARRIOR["AC"]
        if c2 or ((r2 + monster["ATK_MOD"]) >= ac):
            d = dmg(monster.get("COUNTER_DAMAGE_DIE", monster["DMG_DIE"]),
                    monster.get("COUNTER_DAMAGE_MOD", monster["DMG_MOD"]), c2)
            if attacker_is_healer: h_hp -= d
            else:                  w_hp -= d
        marauder_counter_ready = False

    t = 0
    while w_hp > 0 and h_hp > 0 and m_hp > 0:
        if (t % 3) == 0:
            marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))
        actor = order[t % 3]

        if actor == "warrior":
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            def do_one_attack(is_first_attack_of_warrior_turn):
                nonlocal m_hp, cur_streak, max_streak_in_battle, all_streaks
                nonlocal sup_dice, warrior_adv_next
                nonlocal first_warrior_attack_done, first_attack_was_crit, first_attack_was_miss

                has_adv = warrior_adv_next
                warrior_adv_next = False
                use_power = has_adv
                atk_mod = WARRIOR["ATK_MOD"] - (POWER_ATTACK["HIT_PENALTY"] if use_power else 0)
                dmg_mod = WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if use_power else 0)

                r, crit, miss = roll_attack_adv(has_adv)
                final_hit = False
                if not miss:
                    raw_hit = crit or ((r + atk_mod) >= monster_effective_ac(monster))
                    if (not raw_hit) and (sup_dice > 0):
                        need = monster["AC"] - (r + atk_mod)
                        if 1 <= need <= SUPERIORITY_DIE_D:
                            sup_dice -= 1
                            add = roll(SUPERIORITY_DIE_D)
                            raw_hit = crit or ((r + add + atk_mod) >= monster_effective_ac(monster))
                    final_hit = raw_hit

                if is_first_attack_of_warrior_turn and (not first_warrior_attack_done):
                    first_warrior_attack_done = True
                    first_attack_was_crit = crit
                    first_attack_was_miss = (not final_hit)

                if not final_hit:
                    marauder_counter_vs(attacker_is_healer=False)

                if final_hit:
                    extra = 0
                    do_trip = (sup_dice > 0) and (not has_adv) and (m_hp > 0.5 * monster_max_hp)
                    if do_trip:
                        sup_dice -= 1
                        extra = roll(SUPERIORITY_DIE_D)
                        warrior_adv_next = True

                    if crit:
                        dmg_total = roll(w_die) + roll(w_die) + dmg_mod + extra
                        cur_streak += 1
                    else:
                        cur_streak, max_streak_in_battle = end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle)
                        dmg_total = roll(w_die) + dmg_mod + extra
                    m_hp -= dmg_total
                else:
                    cur_streak, max_streak_in_battle = end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle)

            do_one_attack(is_first_attack_of_warrior_turn=True)

            if (m_hp > 0) and (action_surge > 0):
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (m_hp <= 1.2 * expected_next):
                    action_surge -= 1
                    do_one_attack(is_first_attack_of_warrior_turn=False)

        elif actor == "healer":
            if (w_hp >= max_w) and (h_hp >= max_h):
                r, crit, miss = roll_attack()
                if not miss and (crit or (r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster)):
                    m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
            else:
                both_injured = (w_hp < max_w) and (h_hp < max_h)
                someone_low  = (w_hp < max_w * 0.5) or (h_hp < max_h * 0.5)

                def best_available(pred):
                    cand = [lvl for lvl, cnt in slots.items() if cnt > 0 and pred(lvl, cnt)]
                    return max(cand) if cand else 0

                chosen = None
                if both_injured:
                    lvl = best_available(lambda L, C: L >= 3)
                    if lvl >= 3: chosen = ("mass_healing_word", lvl)
                if (chosen is None) and someone_low:
                    lvl = best_available(lambda L, C: True)
                    if lvl >= 1: chosen = ("cure_wounds", lvl)
                if (chosen is None) and ((w_hp < max_w) or (h_hp < max_h)):
                    lvl = best_available(lambda L, C: L <= 2) or best_available(lambda L, C: True)
                    if lvl >= 1: chosen = ("healing_word", lvl)

                if chosen is None:
                    r, crit, miss = roll_attack()
                    if not miss and (crit or (r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster)):
                        m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
                else:
                    spell, lvl = chosen
                    if spell == "mass_healing_word":
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        w_hp = min(max_w, w_hp + heal)
                        h_hp = min(max_h, h_hp + heal)
                    else:
                        target_is_w = (w_hp <= h_hp)
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        if target_is_w: w_hp = min(max_w, w_hp + heal)
                        else:           h_hp = min(max_h, h_hp + heal)
                    slots[lvl] -= 1

        else:  # monster
            if monster.get("REGEN"):
                m_hp = min(monster_max_hp, m_hp + monster["REGEN"])

            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True
                    breath_charges = breath_max_charges

            alive_targets = {}
            if w_hp > 0: alive_targets["w"] = w_hp
            if h_hp > 0: alive_targets["h"] = h_hp

            used_breath, breath_ready, breath_charges, per = try_breath(
                breath_cfg, breath_ready, breath_charges, alive_targets
            )
            if used_breath:
                if "w" in per: w_hp -= per["w"]
                if "h" in per: h_hp -= per["h"]

            if wolf_cfg and (not wolf_summoned) and (m_hp <= monster_max_hp * wolf_cfg["TRIGGER_PCT"]):
                wolf_summoned = True
                wolf_rounds_left = wolf_cfg["DURATION"]

            if wolf_cfg and wolf_rounds_left > 0:
                target_is_h = (h_hp > 0 and (h_hp <= w_hp or w_hp <= 0))
                bite = roll(wolf_cfg["DIE"]) + wolf_cfg["MOD"]
                if target_is_h: h_hp -= bite
                elif w_hp > 0:  w_hp -= bite
                wolf_rounds_left -= 1

            if not used_breath:
                for _ in range(monster.get("ATTACKS", 1)):
                    target_is_h = (h_hp <= w_hp and h_hp > 0) or (w_hp <= 0 and h_hp > 0)
                    r, crit, miss = roll_attack()
                    if not first_monster_attack_done:
                        if crit: received_crit_first_turn = True
                        first_monster_attack_done = True
                    if not miss:
                        target_ac = HEALER["AC"] if target_is_h else WARRIOR["AC"]
                        hit = crit or ((r + monster["ATK_MOD"]) >= target_ac)
                        if hit:
                            d = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                            if crit and monster.get("CRIT_EXTRA_WEAPON_DICE", 0) > 0:
                                d += sum(roll(monster["DMG_DIE"]) for _ in range(monster["CRIT_EXTRA_WEAPON_DICE"]))
                            if target_is_h: h_hp -= d
                            else:           w_hp -= d
        t += 1

    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    party_won = (m_hp <= 0) and (w_hp > 0 or h_hp > 0)
    return dict(
        warrior_won = party_won,
        party_first = party_first,
        first_attack_crit = first_attack_was_crit,
        first_attack_miss = first_attack_was_miss,
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )

# ---------------------------
# Full Party scenario
# ---------------------------
def simulate_battle_full_party(w_die=10, monster=GIANT_APE):
    w_hp = WARRIOR["HP"]; h_hp = HEALER["HP"]; r_hp = ROGUE["HP"]; z_hp = WIZARD["HP"]
    max_w, max_h, max_r, max_z = w_hp, h_hp, r_hp, z_hp

    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False

    healer_slots = dict(HEALER_SLOTS_L10); SPELL_MOD = HEALER["DMG_MOD"]
    wizard_slots = dict(WIZARD_SLOTS_L10)

    order = initiative_order(["warrior", "healer", "rogue", "wizard", "monster"])
    party_first = (min(order.index("warrior"), order.index("healer"), order.index("rogue"), order.index("wizard"))
                   < order.index("monster"))

    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False
    first_monster_attack_done = False
    received_crit_first_turn = False

    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    rogue_uncanny_ready = True
    allies_attacked_this_round = False
    alive_party = lambda: (w_hp > 0) or (h_hp > 0) or (r_hp > 0) or (z_hp > 0)

    monster_max_hp = monster["HP"]
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)
    breath_max_charges = monster.get("BREATH_CHARGES", 1) if breath_cfg else 0
    breath_charges = breath_max_charges if breath_ready else 0
    marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))
    wolf_cfg = monster.get("WOLF")
    wolf_rounds_left = 0
    wolf_summoned = False

    def marauder_counter(attacker_name: str):
        nonlocal w_hp, h_hp, r_hp, z_hp, marauder_counter_ready, rogue_uncanny_ready
        if (not monster.get("COUNTER_ON_MISS")) or (not marauder_counter_ready) or (monster["HP"] <= 0):
            return
        r2, c2, m2 = roll_attack()
        if m2:
            marauder_counter_ready = False
            return
        ac_map = {"warrior": WARRIOR["AC"], "healer": HEALER["AC"], "rogue": ROGUE["AC"], "wizard": WIZARD["AC"]}
        if c2 or ((r2 + monster["ATK_MOD"]) >= ac_map[attacker_name]):
            dmg_amt = dmg(monster.get("COUNTER_DAMAGE_DIE", monster["DMG_DIE"]),
                          monster.get("COUNTER_DAMAGE_MOD", monster["DMG_MOD"]), c2)
            if attacker_name == "rogue" and ROGUE_UNCANNY_DODGE and rogue_uncanny_ready and not c2:
                dmg_amt //= 2
                rogue_uncanny_ready = False
            if   attacker_name == "warrior": w_hp -= dmg_amt
            elif attacker_name == "healer":  h_hp -= dmg_amt
            elif attacker_name == "rogue":   r_hp -= dmg_amt
            else:                            z_hp -= dmg_amt
        marauder_counter_ready = False

    def end_streak():
        nonlocal cur_streak, max_streak_in_battle, all_streaks
        cur_streak, max_streak_local = end_streak_if_any(cur_streak, all_streaks, max_streak_in_battle)
        max_streak_in_battle = max(max_streak_in_battle, max_streak_local)

    def monster_choose_target():
        candidates = []
        if w_hp > 0: candidates.append(("warrior", w_hp, WARRIOR["AC"]))
        if h_hp > 0: candidates.append(("healer",  h_hp, HEALER["AC"]))
        if r_hp > 0: candidates.append(("rogue",   r_hp, ROGUE["AC"]))
        if z_hp > 0: candidates.append(("wizard",  z_hp, WIZARD["AC"]))
        candidates.sort(key=lambda x: (x[1], ["healer","wizard","rogue","warrior"].index(x[0])))
        return candidates[0] if candidates else (None, 0, 0)

    t = 0
    while (monster["HP"] > 0) and alive_party():
        if (t % len(order)) == 0:
            allies_attacked_this_round = False
            rogue_uncanny_ready = True
            marauder_counter_ready = bool(monster.get("COUNTER_ON_MISS"))

        actor = order[t % len(order)]

        if actor == "warrior" and w_hp > 0 and monster["HP"] > 0:
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            def do_one_warrior_attack(is_first):
                nonlocal cur_streak, sup_dice, warrior_adv_next
                nonlocal first_warrior_attack_done, first_attack_was_crit, first_attack_was_miss

                has_adv = warrior_adv_next
                warrior_adv_next = False
                use_power = has_adv
                atk_mod = WARRIOR["ATK_MOD"] - (POWER_ATTACK["HIT_PENALTY"] if use_power else 0)
                dmg_mod = WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if use_power else 0)

                r, crit, miss = roll_attack_adv(has_adv)
                final_hit = False
                if not miss:
                    raw_hit = crit or ((r + atk_mod) >= monster_effective_ac(monster))
                    if (not raw_hit) and (sup_dice > 0):
                        need = monster["AC"] - (r + atk_mod)
                        if 1 <= need <= SUPERIORITY_DIE_D:
                            sup_dice -= 1
                            add = roll(SUPERIORITY_DIE_D)
                            raw_hit = (crit or ((r + add + atk_mod)>= monster_effective_ac(monster)))
                    final_hit = raw_hit

                if is_first and (not first_warrior_attack_done):
                    first_warrior_attack_done = True
                    first_attack_was_crit = crit
                    first_attack_was_miss = (not final_hit)

                if final_hit:
                    extra = 0
                    do_trip = (sup_dice > 0) and (not has_adv) and (monster["HP"] > 0.5 * monster_max_hp)
                    if do_trip:
                        sup_dice -= 1
                        extra = roll(SUPERIORITY_DIE_D)
                        warrior_adv_next = True
                    if crit:
                        total = roll(w_die) + roll(w_die) + dmg_mod + extra
                        cur_streak += 1
                    else:
                        end_streak()
                        total = roll(w_die) + dmg_mod + extra
                    monster["HP"] -= total
                else:
                    end_streak()
                    marauder_counter(attacker_name="warrior")

            do_one_warrior_attack(is_first=True)
            if (monster["HP"] > 0) and (action_surge > 0):
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (monster["HP"] <= 1.2 * expected_next):
                    action_surge -= 1
                    do_one_warrior_attack(is_first=False)

            allies_attacked_this_round = True

        elif actor == "healer" and h_hp > 0 and monster["HP"] > 0:
            if (w_hp >= max_w) and (h_hp >= max_h) and (r_hp >= max_r) and (z_hp >= max_z):
                r, crit, miss = roll_attack()
                if not miss and (crit or (r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster)):
                    monster["HP"] -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
                allies_attacked_this_round = True
            else:
                injured = []
                if w_hp < max_w: injured.append(("warrior", max_w - w_hp))
                if h_hp < max_h: injured.append(("healer",  max_h - h_hp))
                if r_hp < max_r: injured.append(("rogue",   max_r - r_hp))
                if z_hp < max_z: injured.append(("wizard",  max_z - z_hp))

                both_injured = len(injured) >= 2
                someone_low  = (w_hp <= max_w*0.5) or (h_hp <= max_h*0.5) or (r_hp <= max_r*0.5) or (z_hp <= max_z*0.5)

                def best_available(pred):
                    cand = [lvl for lvl,cnt in healer_slots.items() if cnt>0 and pred(lvl,cnt)]
                    return max(cand) if cand else 0

                chosen = None
                if both_injured:
                    lvl = best_available(lambda L,C: L >= 3)
                    if lvl >= 3: chosen = ("mass_healing_word", lvl)
                if (chosen is None) and someone_low:
                    lvl = best_available(lambda L,C: True)
                    if lvl >= 1: chosen = ("cure_wounds", lvl)
                if (chosen is None) and injured:
                    lvl = best_available(lambda L,C: L <= 2) or best_available(lambda L,C: True)
                    if lvl >= 1: chosen = ("healing_word", lvl)

                if chosen is None:
                    r, crit, miss = roll_attack()
                    if not miss and (crit or (r + HEALER["ATK_MOD"])>= monster_effective_ac(monster)):
                        monster["HP"] -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
                    else:
                        marauder_counter(attacker_name="healer")
                    allies_attacked_this_round = True
                else:
                    spell, lvl = chosen
                    if spell == "mass_healing_word":
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        w_hp = min(max_w, w_hp + heal)
                        h_hp = min(max_h, h_hp + heal)
                        r_hp = min(max_r, r_hp + heal)
                        z_hp = min(max_z, z_hp + heal)
                    else:
                        target = min([("warrior", w_hp, max_w), ("healer", h_hp, max_h),
                                      ("rogue", r_hp, max_r), ("wizard", z_hp, max_z)],
                                     key=lambda t: (t[1]/t[2] if t[2]>0 else 1.0))
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        if   target[0] == "warrior": w_hp = min(max_w, w_hp + heal)
                        elif target[0] == "healer":  h_hp = min(max_h, h_hp + heal)
                        elif target[0] == "rogue":   r_hp = min(max_r, r_hp + heal)
                        else:                        z_hp = min(max_z, z_hp + heal)
                    healer_slots[lvl] -= 1

        elif actor == "rogue" and r_hp > 0 and monster["HP"] > 0:
            has_adv = (ROGUE_STEADY_AIM and not allies_attacked_this_round)
            sa_available = has_adv or allies_attacked_this_round
            r, crit, miss = roll_attack_adv(has_adv)
            if not miss and (crit or (r + ROGUE["ATK_MOD"]) >= monster_effective_ac(monster)):
                weapon = (roll(ROGUE["DMG_DIE"]) + (roll(ROGUE["DMG_DIE"]) if crit else 0)) + ROGUE["DMG_MOD"]
                total = weapon
                if sa_available:
                    sa_dice = SNEAK_ATTACK_DICE * (2 if crit else 1)
                    total += sum(roll(SNEAK_ATTACK_DIE) for _ in range(sa_dice))
                monster["HP"] -= total
            else:
                marauder_counter(attacker_name="rogue")
            allies_attacked_this_round = True

        elif actor == "wizard" and z_hp > 0 and monster["HP"] > 0:
            did_attack_roll = False
            high = wizard_highest_slot(wizard_slots)
            if high > 0:
                mm_darts = high + 2
                expected_mm = mm_darts * 3.5
                if monster.get("AUTO_SPELL_RESIST_PCT"): expected_mm *= (1 - monster["AUTO_SPELL_RESIST_PCT"])
                if expected_mm >= monster["HP"]:
                    dmg_mm = wizard_magic_missile_damage(high)
                    if monster.get("AUTO_SPELL_RESIST_PCT"):
                        dmg_mm = int(round(dmg_mm * (1 - monster["AUTO_SPELL_RESIST_PCT"])))
                    monster["HP"] -= dmg_mm
                    wizard_slots[high] -= 1
                else:
                    r, crit, miss = roll_attack()
                    did_attack_roll = True
                    if not miss and (crit or (r + WIZARD["ATK_MOD"]) >= monster_effective_ac(monster, is_spell_attack=True)):
                        monster["HP"] -= wizard_chromatic_orb_damage(high, crit)
                    else:
                        marauder_counter(attacker_name="wizard")
                    wizard_slots[high] -= 1
            else:
                r, crit, miss = roll_attack()
                did_attack_roll = True
                if not miss and (crit or (r + WIZARD["ATK_MOD"]) >= monster_effective_ac(monster, is_spell_attack=True)):
                    monster["HP"] -= wizard_fire_bolt_damage(crit)
                else:
                    marauder_counter(attacker_name="wizard")
            if did_attack_roll:
                allies_attacked_this_round = True

        elif actor == "monster" and monster["HP"] > 0:
            if monster.get("REGEN"):
                monster["HP"] = min(monster_max_hp, monster["HP"] + monster["REGEN"])

            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True
                    breath_charges = breath_max_charges

            alive_targets = {}
            if w_hp > 0: alive_targets["w"] = w_hp
            if h_hp > 0: alive_targets["h"] = h_hp
            if r_hp > 0: alive_targets["r"] = r_hp
            if z_hp > 0: alive_targets["z"] = z_hp

            used_breath, breath_ready, breath_charges, per = try_breath(
                breath_cfg, breath_ready, breath_charges, alive_targets
            )
            if used_breath:
                if "w" in per: w_hp -= per["w"]
                if "h" in per: h_hp -= per["h"]
                if "r" in per: r_hp -= per["r"]
                if "z" in per: z_hp -= per["z"]

            if wolf_cfg and (not wolf_summoned) and (monster["HP"] <= monster_max_hp * wolf_cfg["TRIGGER_PCT"]):
                wolf_summoned = True
                wolf_rounds_left = wolf_cfg["DURATION"]

            if wolf_cfg and wolf_rounds_left > 0:
                tgt_name, _tgt_hp, _tgt_ac = monster_choose_target()
                if tgt_name:
                    bite = roll(wolf_cfg["DIE"]) + wolf_cfg["MOD"]
                    if   tgt_name == "warrior": w_hp -= bite
                    elif tgt_name == "healer":  h_hp -= bite
                    elif tgt_name == "rogue":   r_hp -= bite
                    else:                       z_hp -= bite
                wolf_rounds_left -= 1

            if not used_breath:
                for _ in range(monster.get("ATTACKS", 1)):
                    tgt_name, tgt_hp, tgt_ac = monster_choose_target()
                    if tgt_name is None: break
                    r, crit, miss = roll_attack()
                    if not first_monster_attack_done:
                        if crit: received_crit_first_turn = True
                        first_monster_attack_done = True
                    if miss: continue

                    def apply_damage(amount):
                        nonlocal w_hp, h_hp, r_hp, z_hp, rogue_uncanny_ready
                        dmg_amt = amount
                        if tgt_name == "rogue" and ROGUE_UNCANNY_DODGE and rogue_uncanny_ready and not crit:
                            dmg_amt //= 2
                            rogue_uncanny_ready = False
                        if   tgt_name == "warrior": w_hp -= dmg_amt
                        elif tgt_name == "healer":  h_hp -= dmg_amt
                        elif tgt_name == "rogue":   r_hp -= dmg_amt
                        else:                       z_hp -= dmg_amt

                    would_hit = ((r + monster["ATK_MOD"]) >= tgt_ac) or crit
                    if not would_hit: continue

                    base = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                    if crit and monster.get("CRIT_EXTRA_WEAPON_DICE", 0) > 0:
                        base += sum(roll(monster["DMG_DIE"]) for _ in range(monster["CRIT_EXTRA_WEAPON_DICE"]))

                    if tgt_name == "wizard" and WIZARD_SHIELD_ACTIVE and not crit:
                        within = ((r + monster["ATK_MOD"]) < (tgt_ac + 5)) and ((r + monster["ATK_MOD"]) >= tgt_ac)
                        if within:
                            spent = wizard_spend_lowest_slot(wizard_slots)
                            if spent == 0:
                                apply_damage(base)
                        else:
                            apply_damage(base)
                    else:
                        apply_damage(base)

        t += 1
        if monster["HP"] <= 0 or not alive_party(): break

    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    party_won = (monster["HP"] <= 0) and alive_party()
    return dict(
        warrior_won = party_won,
        party_first = party_first,
        first_attack_crit = first_attack_was_crit,
        first_attack_miss = first_attack_was_miss,
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )

# ---------------------------
# Main
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(description="DnD battle simulator (1v1 / healer / full party)")
    p.add_argument("--monster", type=str, default="CLOAKER",
                   help="Choose: CLOAKER | BLUE_SLAAD | GIANT_APE | YOUNG_BLUE_DRAGON | ABERRANT_SCREECHER | DOOM_MARAUDER")
    p.add_argument("--all-monsters", action="store_true",
                   help="Run all scenarios for every monster.")
    p.add_argument("--sims", type=int, default=10_000,
                   help="Number of simulations per die per scenario (default 10000).")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed (default 42).")
    return p.parse_args()

def _sanitize_filename(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in s)

def _numeric_metrics(rows: list[dict]) -> list[str]:
    # take keys from first row that are numeric in all rows
    metrics = []
    for k, v in rows[0].items():
        if k == "warrior_die":
            continue
        if all(isinstance(r.get(k), (int, float)) for r in rows):
            metrics.append(k)
    return metrics

def _ensure_same_dice(rows: list[dict]) -> list[str]:
    return [r["warrior_die"] for r in rows]

def plot_per_monster(monster_key: str,
                     rows_solo: list[dict],
                     rows_heal: list[dict],
                     rows_full: list[dict]):
    dice_labels = _ensure_same_dice(rows_solo)  # assumes same dice order across scenarios
    x = np.arange(len(dice_labels))
    width = 0.27

    metrics = _numeric_metrics(rows_solo)  # same schema for all three
    # One graph per metric
    for metric in metrics:
        y_solo  = [r[metric] for r in rows_solo]
        y_heal  = [r[metric] for r in rows_heal]
        y_full  = [r[metric] for r in rows_full]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(x - width, y_solo,  width, label="Solo")
        ax.bar(x,          y_heal, width, label="Healer")
        ax.bar(x + width,  y_full, width, label="Full Party")

        ax.set_xlabel("Damage Die")
        ax.set_ylabel("Data Value")
        ax.set_title(f"{metric} - {monster_key}")
        ax.set_xticks(x, dice_labels)
        ax.legend()
        fig.tight_layout()

        fname = f"plot_{_sanitize_filename(metric)}_{monster_key}.png"
        fig.savefig(fname, dpi=150)
        plt.close(fig)
        
# Plot all monsters together for each metric & scenario
def plot_all_monsters(results_by_monster: dict[str, dict[str, list[dict]]]):
    if not results_by_monster:
        return

    # Pick any monster to derive metric keys & dice labels
    sample_monster = next(iter(results_by_monster))
    dice_labels = _ensure_same_dice(results_by_monster[sample_monster]['solo'])
    n_dice = len(dice_labels)
    metrics = _numeric_metrics(results_by_monster[sample_monster]['solo'])

    team_keys = [("solo", "Solo"), ("healer", "Healer"), ("full", "Full Party")]
    monsters = list(results_by_monster.keys())
    x = np.arange(len(monsters))
    width = 0.8 / n_dice  # fit all dice per monster nicely

    for metric in metrics:
        for team_key, team_label in team_keys:
            fig, ax = plt.subplots(figsize=(12, 6))
            # For each die, plot a bar per monster with an offset
            for i, dlabel in enumerate(dice_labels):
                # Gather y across monsters for this die and team
                ys = []
                for m in monsters:
                    rows = results_by_monster[m][team_key]
                    # rows are ordered by dice; get the index by label safely
                    idx = [row["warrior_die"] for row in rows].index(dlabel)
                    ys.append(rows[idx][metric])
                ax.bar(x + (i - (n_dice-1)/2) * width, ys, width, label=dlabel if i == 0 else None)

            ax.set_xlabel("Monster")
            ax.set_ylabel("Data Value")
            ax.set_title(f"{metric} - All Monsters - {team_label}")
            ax.set_xticks(x, monsters)
            # Single legend showing dice labels (attach only once)
            handles, _ = ax.get_legend_handles_labels()
            if handles:
                ax.legend(title="Damage Die")
            fig.tight_layout()

            fname = f"final_{_sanitize_filename(metric)}_{_sanitize_filename(team_key)}_all_monsters.png"
            fig.savefig(fname, dpi=150)
            plt.close(fig)

def run_suite_for_monster(monster_key: str, n_sims: int):
    monster = MONSTERS[monster_key]
    rows_1v1  = [summarize_many(simulate_battle_1v1,         d, monster, n_sims) for d in DICE_TO_TEST]
    rows_heal = [summarize_many(simulate_battle_with_healer, d, monster, n_sims) for d in DICE_TO_TEST]
    rows_full = [summarize_many(simulate_battle_full_party,  d, monster, n_sims) for d in DICE_TO_TEST]

    suffix = f"_{monster_key}" if monster_key else ""
    write_csv(f"dnd_1v1_summaries{suffix}.csv", rows_1v1)
    write_csv(f"dnd_healer_summaries{suffix}.csv", rows_heal)
    write_csv(f"dnd_fullparty_summaries{suffix}.csv", rows_full)

    # Per-monster grouped bar charts
    plot_per_monster(monster_key, rows_1v1, rows_heal, rows_full)

    print(f"Monster selected: {monster_key}")
    print("---- 1v1 summaries ----")
    for r in rows_1v1: print(r)
    print("\n---- Healer summaries ----")
    for r in rows_heal: print(r)
    print("\n---- Full Party summaries ----")
    for r in rows_full: print(r)
    print(f"\nFiles written: dnd_1v1_summaries{suffix}.csv, dnd_healer_summaries{suffix}.csv, dnd_fullparty_summaries{suffix}.csv\n")

    # Return for final all-monsters plots
    return {"solo": rows_1v1, "healer": rows_heal, "full": rows_full}

def main():
    args = parse_args()
    random.seed(args.seed)

    if args.all_monsters:
        results_by_monster = {}
        for key in MONSTERS.keys():
            results_by_monster[key] = run_suite_for_monster(key, args.sims)
        # Final comparison plots across monsters for each metric & team
        plot_all_monsters(results_by_monster)
        print("Final cross-monster comparison plots written (see files starting with 'final_').")
    else:
        monster, mname = get_monster(args.monster)
        run_suite_for_monster(mname, args.sims)

def get_monster(name: str):
    key = name.strip().upper().replace(" ", "_")
    if key in MONSTERS:
        return MONSTERS[key], key
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
    return MONSTERS["CLOAKER"], "CLOAKER"

if __name__ == "__main__":
    main()