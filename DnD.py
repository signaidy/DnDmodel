import random, math, statistics, csv, argparse

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
WARRIOR_CON_MOD = 2  # not directly used now, but handy if you want
SECOND_WIND_THRESHOLD = 0.35   # heal when HP <= 35% of max
ACTION_SURGE_USES = 1
SUPERIORITY_DICE_N = 4         # Battlemaster dice count (lvl 10)
SUPERIORITY_DIE_D = 10         # d10 at lvl 10
POWER_ATTACK = dict(HIT_PENALTY=5, DMG_BONUS=10)  # GWM-like toggle (used when advantaged)


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
#Rogue - HP: 80, AC: 16, ATK_MOD: 6, DMG_MOD: 3, DMG_DIE: 8
ROGUE   = dict(HP=80, AC=16, ATK_MOD=6, DMG_MOD=3, DMG_DIE=8)

# Rogue abilities
ROGUE_LEVEL = 10
SNEAK_ATTACK_DICE = 5      # 5d6 at level 10 (doubles on crit)
SNEAK_ATTACK_DIE  = 6
ROGUE_STEADY_AIM = True    # if no ally has acted before Rogue this round, Rogue uses Steady Aim -> advantage
ROGUE_UNCANNY_DODGE = True # once per round, halve damage from one monster hit on Rogue

#Wizard - HP: 60, AC: 12, ATK_MOD: 4, DMG_MOD: 5, DMG_DIE: 6
WIZARD  = dict(HP=60, AC=12, ATK_MOD=4, DMG_MOD=5, DMG_DIE=6)

# Wizard spell slots for level 10
WIZARD_SLOTS_L10 = {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}

# Wizard combat kit (kept simple & consistent with attack-roll model)
# - Chromatic Orb (attack roll): (slot+2)d8 damage on hit; crit doubles dice. Costs chosen slot.
# - Magic Missile (auto-hit): darts = slot+2; each dart = 1d4+1; good finisher; costs chosen slot.
# - Fire Bolt cantrip (attack roll): 3d10 damage at level 10; crit doubles dice; no slot cost.
# - Shield reaction: +5 AC vs a single attack; if the attack would hit but within +5, spend the lowest slot to negate.
WIZARD_CANTRIP_DICE  = 2   # Fire Bolt scales to 3d10 at lvl 11; at lvl 10 it's 2d10 in RAW
WIZARD_CANTRIP_DIE   = 10
WIZARD_SHIELD_ACTIVE = True

def wizard_spend_lowest_slot(slots: dict) -> int:
    """Spend the lowest-level slot available. Return level spent or 0 if none."""
    for lvl in sorted(slots):
        if slots[lvl] > 0:
            slots[lvl] -= 1
            return lvl
    return 0

def wizard_highest_slot(slots: dict) -> int:
    """Highest slot level available (0 if none)."""
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

# --- Official monster abilities (abstracted to this sim) ---
# Cloaker: two swings
CLOAKER.update(dict(
    ATTACKS=2
))

# Blue Slaad: 3 swings, light spell resistance, regeneration
BLUE_SLAAD.update(dict(
    ATTACKS=3,
    REGEN=10,                      # heals at start of its turn, up to max
    SPELL_RESIST_AC_BONUS=2        # +2 AC vs spell attacks (Chromatic Orb / Fire Bolt)
))

# Giant Ape: two swings, extra weapon die on crit
GIANT_APE.update(dict(
    ATTACKS=2,
    CRIT_EXTRA_WEAPON_DICE=1       # add +1 DMG_DIE on crit (approx. brutish crits)
))

# Young Blue Dragon: 2 swings, Lightning Breath (AOE) with recharge 5-6
YOUNG_BLUE_DRAGON.update(dict(
    ATTACKS=2,
    BREATH=dict(
        N_DICE=8,                  # 8d10 lightning (abstracted)
        DIE=10,
        RECHARGE=[5, 6],           # recharge on 5-6 at start of its turn
        SAVE_SUCCESS_P=0.5         # each target 50% to halve damage (simple stand-in for Dex save)
    )
))

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

def monster_effective_ac(mon, is_spell_attack=False):
    ac = mon["AC"]
    if is_spell_attack:
        ac += mon.get("SPELL_RESIST_AC_BONUS", 0)
    return ac

# ---------------------------
# Dice helpers
# ---------------------------
def roll(d): return random.randint(1, d)

def roll_attack():
    r = roll(20)
    return r, (r == 20), (r == 1)  # value, is_crit, is_crit_miss

def dmg(die, mod, crit=False):
    return (roll(die) + roll(die) + mod) if crit else (roll(die) + mod)

def roll_attack_adv(has_adv: bool):
    if not has_adv:
        r = roll(20)
        return r, (r == 20), (r == 1)
    r1, r2 = roll(20), roll(20)
    crit = (r1 == 20) or (r2 == 20)
    miss = (r1 == 1) and (r2 == 1)
    r = max(r1, r2)
    return r, crit, miss

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
    max_w = WARRIOR["HP"]

    order = initiative_order(["warrior", "monster"])
    party_first = (order[0] == "warrior") # <- clave unificada

    # Warrior resources / state
    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False  # granted by Trip Attack for the NEXT attack
    
    # Monster resources / state
    monster_max_hp = monster["HP"]       # cap for regen
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)

    # First-attack flags (computed AFTER abilities resolution)
    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False

    # Monster first-turn crit flag
    first_monster_attack_done = False
    received_crit_first_turn = False

    # Crit streak tracking (warrior)
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    turn = 0
    while w_hp > 0 and m_hp > 0:
        actor = order[turn % 2]
        if actor == "warrior":
            # --- Second Wind (bonus-like): heal when low, does not consume attack here ---
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            # We may take 1 or 2 attacks (if Action Surge triggers)
            attacks_this_turn = 1

            # Closure to perform one attack with abilities
            def do_one_attack(is_first_attack_of_warrior_turn):
                nonlocal m_hp, cur_streak, max_streak_in_battle, all_streaks
                nonlocal sup_dice, warrior_adv_next
                nonlocal first_warrior_attack_done, first_attack_was_crit, first_attack_was_miss

                # Advantage only if granted from a prior Trip Attack
                has_adv = warrior_adv_next
                warrior_adv_next = False  # consume it

                # Decide Power Attack only when advantaged
                use_power = has_adv
                atk_mod = WARRIOR["ATK_MOD"] - (POWER_ATTACK["HIT_PENALTY"] if use_power else 0)
                dmg_mod = WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if use_power else 0)

                # Roll attack (with possible advantage)
                r, crit, miss = roll_attack_adv(has_adv)
                raw_hit = False
                final_hit = False

                if not miss:
                    # Check raw hit vs AC
                    raw_hit = crit or ((r + atk_mod) >= monster_effective_ac(monster))

                   # Precision Strike: salvage misses by <= d10 if resources remain
                    if (not raw_hit) and (sup_dice > 0):
                        need = monster["AC"] - (r + atk_mod)
                        if 1 <= need <= SUPERIORITY_DIE_D:
                            sup_dice -= 1
                            add = roll(SUPERIORITY_DIE_D)
                            raw_hit = crit or ((r + add + atk_mod) >= monster_effective_ac(monster))
                    final_hit = raw_hit

                # Record first-attack flags AFTER resolution with abilities
                if is_first_attack_of_warrior_turn and (not first_warrior_attack_done):
                    first_warrior_attack_done = True
                    first_attack_was_crit = crit
                    first_attack_was_miss = (not final_hit)

                if final_hit:
                    # Trip Attack: add damage and grant advantage next attack if we have dice
                    extra = 0
                    do_trip = (sup_dice > 0) and (not has_adv) and (m_hp > 0.5 * monster_max_hp)
                    if do_trip:
                        sup_dice -= 1
                        extra = roll(SUPERIORITY_DIE_D)
                        warrior_adv_next = True  # grants adv on NEXT attack

                    if crit:
                        # crit doubles weapon dice only (we won't double the superiority die)
                        dmg_total = roll(w_die) + roll(w_die) + dmg_mod + extra
                        cur_streak += 1
                    else:
                        if cur_streak > 0:
                            all_streaks.append(cur_streak)
                            max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                            cur_streak = 0
                        dmg_total = roll(w_die) + dmg_mod + extra

                    m_hp -= dmg_total
                else:
                    # miss: end any ongoing streak
                    if cur_streak > 0:
                        all_streaks.append(cur_streak)
                        max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                        cur_streak = 0

            # First attack
            do_one_attack(is_first_attack_of_warrior_turn=True)

            # Consider Action Surge for a second attack right now
            if (m_hp > 0) and (action_surge > 0):
                # Heuristic: surge if (i) we crit OR (ii) we can likely finish now
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (m_hp <= 1.2 * expected_next):
                    action_surge -= 1
                    attacks_this_turn += 1

            if attacks_this_turn == 2 and m_hp > 0:
                do_one_attack(is_first_attack_of_warrior_turn=False)

        else:
        # --- Monster turn: Regen -> Recharge -> Breath (optional) -> Multiattack ---
            # Regen (e.g., Blue Slaad)
            if monster.get("REGEN"):
                m_hp = min(monster_max_hp, m_hp + monster["REGEN"])

            # Breath recharge
            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True

            used_breath = False
            if breath_cfg and breath_ready:
                # 1v1: breath still hurts; use it simply when ready
                dmg_breath = sum(roll(breath_cfg["DIE"]) for _ in range(breath_cfg["N_DICE"]))
                # simple "save": 50% to halve
                if random.random() < breath_cfg["SAVE_SUCCESS_P"]:
                    dmg_breath //= 2
                w_hp -= dmg_breath
                breath_ready = False
                used_breath = True

            if not used_breath:
                attacks = monster.get("ATTACKS", 1)
                for _ in range(attacks):
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

    # Warrior resources / state
    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False
    
    # Monster resources / state
    monster_max_hp = monster["HP"]       # cap for regen
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)

    # Flags para condiciones (del GUERRERO y del 1er ataque del MONSTRUO)
    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False

    # Monster first-turn crit
    first_monster_attack_done = False
    received_crit_first_turn = False

    # Racha de críticos del guerrero
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    def best_available(predicate):
        candidates = [lvl for lvl, cnt in slots.items() if cnt > 0 and predicate(lvl, cnt)]
        return max(candidates) if candidates else 0

    t = 0
    while w_hp > 0 and h_hp > 0 and m_hp > 0:
        actor = order[t % 3]
        if actor == "warrior":
            # Second Wind (bonus-like)
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            # Attack (and maybe Action Surge)
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
                raw_hit = False
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
                        if cur_streak > 0:
                            all_streaks.append(cur_streak)
                            max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                            cur_streak = 0
                        dmg_total = roll(w_die) + dmg_mod + extra
                    m_hp -= dmg_total
                else:
                    if cur_streak > 0:
                        all_streaks.append(cur_streak)
                        max_streak_in_battle = max(max_streak_in_battle, cur_streak)
                        cur_streak = 0

            # First attack
            do_one_attack(is_first_attack_of_warrior_turn=True)

            # Action Surge?
            if (m_hp > 0) and (action_surge > 0):
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (m_hp <= 1.2 * expected_next):
                    action_surge -= 1
                    do_one_attack(is_first_attack_of_warrior_turn=False)

        elif actor == "healer":
            if (w_hp >= max_w) and (h_hp >= max_h):
                r, crit, miss = roll_attack()
                if not miss:
                    hit = crit or ((r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster))
                    if hit:
                        m_hp -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
            else:
                both_injured = (w_hp < max_w) and (h_hp < max_h)
                someone_low  = (w_hp < max_w * 0.5) or (h_hp < max_h * 0.5)

                chosen = None
                if both_injured:
                    lvl = best_available(lambda L, C: L >= 3)
                    if lvl >= 3:
                        chosen = ("mass_healing_word", lvl)
                if (chosen is None) and someone_low:
                    lvl = best_available(lambda L, C: True)
                    if lvl >= 1:
                        chosen = ("cure_wounds", lvl)
                if (chosen is None) and ((w_hp < max_w) or (h_hp < max_h)):
                    lvl = best_available(lambda L, C: L <= 2)
                    if lvl == 0:
                        lvl = best_available(lambda L, C: True)
                    if lvl >= 1:
                        chosen = ("healing_word", lvl)

                if chosen is None:
                    r, crit, miss = roll_attack()
                    if not miss:
                        hit = crit or ((r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster))
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
            # Regen
            if monster.get("REGEN"):
                m_hp = min(monster_max_hp, m_hp + monster["REGEN"])

            # Breath recharge
            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True

            used_breath = False
            alive_targets = int(w_hp > 0) + int(h_hp > 0)

            if breath_cfg and breath_ready and alive_targets >= 2:
                # Breath AOE: apply to each alive party member
                dmg_breath = sum(roll(breath_cfg["DIE"]) for _ in range(breath_cfg["N_DICE"]))
                if w_hp > 0:
                    d = dmg_breath
                    if random.random() < breath_cfg["SAVE_SUCCESS_P"]: d //= 2
                    w_hp -= d
                if h_hp > 0:
                    d = dmg_breath
                    if random.random() < breath_cfg["SAVE_SUCCESS_P"]: d //= 2
                    h_hp -= d
                breath_ready = False
                used_breath = True

            if not used_breath:
                attacks = monster.get("ATTACKS", 1)
                for _ in range(attacks):
                    target_is_h = (h_hp <= w_hp and h_hp > 0) or (w_hp <= 0 and h_hp > 0)  # prefer lower HP alive
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
# Full Party scenario
# ---------------------------

def simulate_battle_full_party(w_die=10, monster=GIANT_APE):
    # Party state
    w_hp = WARRIOR["HP"]
    h_hp = HEALER["HP"]
    r_hp = ROGUE["HP"]
    z_hp = WIZARD["HP"]
    max_w, max_h, max_r, max_z = w_hp, h_hp, r_hp, z_hp

    # Resources (per-fight)
    # Warrior (from your 1v1/healer sims)
    action_surge = ACTION_SURGE_USES
    second_wind_available = True
    sup_dice = SUPERIORITY_DICE_N
    warrior_adv_next = False

    # Healer
    healer_slots = dict(HEALER_SLOTS_L10)
    SPELL_MOD = HEALER["DMG_MOD"]

    # Wizard
    wizard_slots = dict(WIZARD_SLOTS_L10)

    # Initiative (5 actors)
    order = initiative_order(["warrior", "healer", "rogue", "wizard", "monster"])
    party_first = (min(order.index("warrior"), order.index("healer"), order.index("rogue"), order.index("wizard"))
                   < order.index("monster"))

    # First-attack flags (warrior)
    first_warrior_attack_done = False
    first_attack_was_crit = False
    first_attack_was_miss = False

    # First monster attack crit?
    first_monster_attack_done = False
    received_crit_first_turn = False

    # Streaks for warrior only (to keep metrics consistent)
    cur_streak = 0
    max_streak_in_battle = 0
    all_streaks = []

    # Rogue reaction: Uncanny Dodge once per round
    rogue_uncanny_ready = True

    # "Round" bookkeeping: reset at start of each cycle through initiative
    allies_attacked_this_round = False  # for Rogue Sneak Attack logic
    alive_party = lambda: (w_hp > 0) or (h_hp > 0) or (r_hp > 0) or (z_hp > 0)
    
    # Monster resources / state
    monster_max_hp = monster["HP"]       # cap for regen
    breath_cfg = monster.get("BREATH")
    breath_ready = bool(breath_cfg)

    def end_streak_if_any():
        nonlocal cur_streak, max_streak_in_battle, all_streaks
        if cur_streak > 0:
            all_streaks.append(cur_streak)
            max_streak_in_battle = max(max_streak_in_battle, cur_streak)
            cur_streak = 0

    # Helper: single-target monster choice (lowest HP among alive; tiebreaker order)
    def monster_choose_target():
        candidates = []
        if w_hp > 0: candidates.append(("warrior", w_hp, WARRIOR["AC"]))
        if h_hp > 0: candidates.append(("healer",  h_hp, HEALER["AC"]))
        if r_hp > 0: candidates.append(("rogue",   r_hp, ROGUE["AC"]))
        if z_hp > 0: candidates.append(("wizard",  z_hp, WIZARD["AC"]))
        # Lowest current HP; tie-breaker order healer -> wizard -> rogue -> warrior (squishies first)
        candidates.sort(key=lambda x: (x[1], ["healer","wizard","rogue","warrior"].index(x[0])))
        return candidates[0] if candidates else (None, 0, 0)

    t = 0
    while (monster["HP"] > 0) and alive_party():
        if (t % len(order)) == 0:
            # New round
            allies_attacked_this_round = False
            rogue_uncanny_ready = True

        actor = order[t % len(order)]

        if actor == "warrior" and w_hp > 0 and monster["HP"] > 0:
            # Second Wind (bonus-like)
            if second_wind_available and (w_hp <= max_w * SECOND_WIND_THRESHOLD):
                w_hp = min(max_w, w_hp + roll(10) + WARRIOR_LEVEL)
                second_wind_available = False

            def do_one_warrior_attack(is_first):
                nonlocal cur_streak, max_streak_in_battle, all_streaks
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
                        dmg_total = roll(w_die) + roll(w_die) + dmg_mod + extra
                        cur_streak += 1
                    else:
                        end_streak_if_any()
                        dmg_total = roll(w_die) + dmg_mod + extra
                    monster["HP"] -= dmg_total
                else:
                    end_streak_if_any()

            do_one_warrior_attack(is_first=True)
            if (monster["HP"] > 0) and (action_surge > 0):
                avg_weapon = (w_die + 1) / 2
                expected_next = avg_weapon + WARRIOR["DMG_MOD"] + (POWER_ATTACK["DMG_BONUS"] if warrior_adv_next else 0)
                if first_attack_was_crit or (monster["HP"] <= 1.2 * expected_next):
                    action_surge -= 1
                    do_one_warrior_attack(is_first=False)

            allies_attacked_this_round = True

        elif actor == "healer" and h_hp > 0 and monster["HP"] > 0:
            # Attack if everyone full; else heal using 5e-like slots & logic
            if (w_hp >= max_w) and (h_hp >= max_h) and (r_hp >= max_r) and (z_hp >= max_z):
                r, crit, miss = roll_attack()
                if not miss and (crit or (r + HEALER["ATK_MOD"]) >= monster_effective_ac(monster)):
                    monster["HP"] -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
                allies_attacked_this_round = True
            else:
                # Healing priorities
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
                    # fallback attack
                    r, crit, miss = roll_attack()
                    if not miss and (crit or (r + HEALER["ATK_MOD"])>= monster_effective_ac(monster)):
                        monster["HP"] -= dmg(HEALER["DMG_DIE"], HEALER["DMG_MOD"], crit)
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
                        # heal lowest current HP
                        injured.sort(key=lambda x: x[1], reverse=True)  # most missing first
                        target = min([("warrior", w_hp, max_w), ("healer", h_hp, max_h),
                                      ("rogue", r_hp, max_r), ("wizard", z_hp, max_z)],
                                     key=lambda t: (t[1]/t[2] if t[2]>0 else 1.0))
                        heal = heal_amount(spell, lvl, SPELL_MOD)
                        if target[0] == "warrior": w_hp = min(max_w, w_hp + heal)
                        elif target[0] == "healer": h_hp = min(max_h, h_hp + heal)
                        elif target[0] == "rogue":  r_hp = min(max_r, r_hp + heal)
                        else:                       z_hp = min(max_z, z_hp + heal)
                    healer_slots[lvl] -= 1  # consume slot

        elif actor == "rogue" and r_hp > 0 and monster["HP"] > 0:
            # Advantage if Steady Aim (no ally before rogue this round) or if an ally already attacked
            has_adv = allies_attacked_this_round or (ROGUE_STEADY_AIM and not allies_attacked_this_round)

            r, crit, miss = roll_attack_adv(has_adv)
            if not miss and (crit or (r + ROGUE["ATK_MOD"]) >= monster_effective_ac(monster)):
                # Weapon damage
                weapon = (roll(ROGUE["DMG_DIE"]) + (roll(ROGUE["DMG_DIE"]) if crit else 0)) + ROGUE["DMG_MOD"]
                # Sneak Attack (once per turn): available due to adv or ally engagement
                sa_dice = SNEAK_ATTACK_DICE * (2 if crit else 1)
                sneak = sum(roll(SNEAK_ATTACK_DIE) for _ in range(sa_dice))
                monster["HP"] -= (weapon + sneak)
            allies_attacked_this_round = True

        elif actor == "wizard" and z_hp > 0 and monster["HP"] > 0:
            # Choose spell: finish with Magic Missile if its expected damage >= remaining HP, else Chromatic Orb with highest slot, else Fire Bolt.
            high = wizard_highest_slot(wizard_slots)
            if high > 0:
                # Expected MM damage
                mm_darts = high + 2
                expected_mm = mm_darts * 3.5  # E[1d4+1]=3.5
                if expected_mm >= monster["HP"]:
                    # Finish with Magic Missile (auto-hit)
                    dmg_mm = wizard_magic_missile_damage(high)
                    monster["HP"] -= dmg_mm
                    wizard_slots[high] -= 1
                else:
                    # Chromatic Orb (attack roll, crit doubles dice)
                    r, crit, miss = roll_attack()
                    if not miss and (crit or (r + WIZARD["ATK_MOD"]) >= monster_effective_ac(monster, is_spell_attack=True)):
                        monster["HP"] -= wizard_chromatic_orb_damage(high, crit)
                    # spend slot regardless of hit/miss
                    wizard_slots[high] -= 1
            else:
                # Fire Bolt cantrip (attack roll)
                r, crit, miss = roll_attack()
                if not miss and (crit or (r + WIZARD["ATK_MOD"]) >= monster_effective_ac(monster, is_spell_attack=True)):
                    monster["HP"] -= wizard_fire_bolt_damage(crit)
            allies_attacked_this_round = True

        elif actor == "monster" and monster["HP"] > 0:
            # Regen up to max
            if monster.get("REGEN"):
                monster["HP"] = min(monster_max_hp, monster["HP"] + monster["REGEN"])

            # Recharge breath
            if breath_cfg and not breath_ready:
                if roll(6) in breath_cfg["RECHARGE"]:
                    breath_ready = True

            # Count alive targets
            alive = []
            if w_hp > 0: alive.append(("warrior", WARRIOR["AC"]))
            if h_hp > 0: alive.append(("healer",  HEALER["AC"]))
            if r_hp > 0: alive.append(("rogue",   ROGUE["AC"]))
            if z_hp > 0: alive.append(("wizard",  WIZARD["AC"]))

            used_breath = False
            if breath_cfg and breath_ready and len(alive) >= 2:
                dmg_breath = sum(roll(breath_cfg["DIE"]) for _ in range(breath_cfg["N_DICE"]))
                for name, _ac in alive:
                    d = dmg_breath
                    if random.random() < breath_cfg["SAVE_SUCCESS_P"]:
                        d //= 2
                    if name == "warrior": w_hp -= d
                    elif name == "healer": h_hp -= d
                    elif name == "rogue":  r_hp -= d
                    else:                  z_hp -= d
                breath_ready = False
                used_breath = True

            if not used_breath:
                attacks = monster.get("ATTACKS", 1)
                for _ in range(attacks):
                    # choose lowest HP alive (healer>wizard>rogue>warrior tiebreaker)
                    tgt_name, tgt_hp, tgt_ac = monster_choose_target()
                    if tgt_name is None: break

                    r, crit, miss = roll_attack()
                    if not first_monster_attack_done:
                        if crit: received_crit_first_turn = True
                        first_monster_attack_done = True

                    if miss:
                        continue

                    # Wizard Shield reaction: negate if within +5 and slots available (no crit negation)
                    def apply_damage(amount):
                        nonlocal w_hp, h_hp, r_hp, z_hp, rogue_uncanny_ready
                        dmg_amt = amount
                        # Rogue Uncanny Dodge (halve once per round, non-crit)
                        if tgt_name == "rogue" and ROGUE_UNCANNY_DODGE and rogue_uncanny_ready and not crit:
                            dmg_amt //= 2
                            rogue_uncanny_ready = False
                        if tgt_name == "warrior": w_hp -= dmg_amt
                        elif tgt_name == "healer": h_hp -= dmg_amt
                        elif tgt_name == "rogue":  r_hp -= dmg_amt
                        else:                      z_hp -= dmg_amt

                    would_hit = ((r + monster["ATK_MOD"]) >= tgt_ac) or crit
                    if not would_hit:
                        continue

                    # Compute base damage (with crit extra die if configured)
                    base = dmg(monster["DMG_DIE"], monster["DMG_MOD"], crit)
                    if crit and monster.get("CRIT_EXTRA_WEAPON_DICE", 0) > 0:
                        base += sum(roll(monster["DMG_DIE"]) for _ in range(monster["CRIT_EXTRA_WEAPON_DICE"]))

                    if tgt_name == "wizard" and WIZARD_SHIELD_ACTIVE and not crit:
                        # if within +5, try to spend a slot to negate
                        within = ((r + monster["ATK_MOD"]) < (tgt_ac + 5)) and ((r + monster["ATK_MOD"]) >= tgt_ac)
                        if within:
                            spent = wizard_spend_lowest_slot(wizard_slots)
                            if spent > 0:
                                # negated
                                pass
                            else:
                                apply_damage(base)
                        else:
                            apply_damage(base)
                    else:
                        apply_damage(base)

        # Next turn
        t += 1

        # End early if monster dies
        if monster["HP"] <= 0:
            break
        # Or if party wiped
        if not alive_party():
            break

    # close any streak
    if cur_streak > 0:
        all_streaks.append(cur_streak)
        max_streak_in_battle = max(max_streak_in_battle, cur_streak)

    party_won = (monster["HP"] <= 0) and alive_party()
    return dict(
        warrior_won = party_won,
        party_first = party_first,
        first_attack_crit = first_attack_was_crit,      # warrior
        first_attack_miss = first_attack_was_miss,      # warrior
        received_crit_first_turn = received_crit_first_turn,
        crit_streaks = all_streaks if all_streaks else [0],
        max_streak = max_streak_in_battle if max_streak_in_battle > 0 else 0
    )
    
def simulate_many_full_party(w_die, monster=GIANT_APE):
    # Copy the monster statblock per sim so we don't mutate the global
    results = []
    for _ in range(N_SIMS):
        m = dict(monster)  # local copy with its own HP
        results.append(simulate_battle_full_party(w_die, m))

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
            
        # C) Full Party scenario (mismos campos/condicionales)
    rows_full = [simulate_many_full_party(d, monster=monster) for d in DICE_TO_TEST]
    with open("dnd_fullparty_summaries.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_full[0].keys()))
        w.writeheader()
        for r in rows_full:
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
    print("\n---- Full Party summaries ----")
    for r in rows_full: print(r)
    print("\nFiles written: dnd_1v1_summaries.csv, dnd_healer_summaries.csv, dnd_fullparty_summaries.csv")

if __name__ == "__main__":
    main()