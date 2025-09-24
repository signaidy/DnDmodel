

# DnD Battle Simulator & Plotter

Monte-Carlo simulator that pits a level-10 party (Warrior, optional Healer, optional Rogue & Wizard) against various monsters across different weapon damage dice. It writes CSV summaries and grouped-bar charts for quick visual comparison.

## Setup

### 1) Prereqs

* Python **3.10+** (uses modern type hints and `pathlib`)

### 2) Create a virtual environment and install deps

**Windows (PowerShell)**

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install numpy matplotlib
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install numpy matplotlib
```

> The code forces the non-GUI Matplotlib backend (`Agg`), so it works headless.

## Run

From the project root (with the venv activated):

### Single monster

```bash
python DnD.py --monster CLOAKER --sims 20000 --seed 123
```

### All monsters

```bash
python DnD.py --all-monsters --sims 10000
```

Outputs are organized under:

```
csv/
  <MONSTER>/
    dnd_1v1_summaries.csv
    dnd_healer_summaries.csv
    dnd_fullparty_summaries.csv

graphs/
  <MONSTER>/
    plot_<metric>_<MONSTER>.png
  _ALL_MONSTERS/
    final_<metric>_<team>_all_monsters.png
```

## Options

* `--monster <NAME>`
  Choose one monster by key. Valid keys:
  `CLOAKER | BLUE_SLAAD | GIANT_APE | YOUNG_BLUE_DRAGON | ABERRANT_SCREECHER | DOOM_MARAUDER`
  Aliases: `BLUE/SLAAD -> BLUE_SLAAD`, `APE -> GIANT_APE`, `DRAGON -> YOUNG_BLUE_DRAGON`, `SCREECHER -> ABERRANT_SCREECHER`, `DOOM -> DOOM_MARAUDER`.

* `--all-monsters`
  Run every scenario for **all** monsters and also produce cross-monster comparison charts.

* `--sims <N>`
  Number of Monte-Carlo simulations per damage die per scenario (default `10000`). Larger = smoother estimates, slower runtime.

* `--seed <INT>`
  RNG seed (default `42`) for reproducibility.

## What you get

### CSV columns (per die, per scenario)

For each damage die (d4, d6, …), the simulator records:

* `warrior_die` — e.g., `d8`
* `wins`, `losses` — count out of `--sims`
* `baseline_P(win)` — overall win rate
* `P(win | party first)` — win rate when party wins initiative
* `P(win | first attack crit)` — win rate when the **first** party attack crits
* `ΔP(win) if first attack missed` — (conditional win rate given miss) − baseline
* `ΔP(win) if received crit on monster first turn` — (conditional win rate) − baseline
* `crit_streak_min`, `crit_streak_max`, `crit_streak_avg>0` — distribution of positive crit streaks within fights

Three CSVs per monster:

* `dnd_1v1_summaries.csv` (warrior solo)
* `dnd_healer_summaries.csv` (warrior + healer)
* `dnd_fullparty_summaries.csv` (full party: warrior, healer, rogue, wizard)

### Plots

#### Per-monster plots (in `graphs/<MONSTER>/`)

* **One PNG per metric** (e.g., `plot_baseline_P_win_GIANT_APE.png`).
* **X-axis:** damage die (`d4…d20`).
* **Bars:** 3 grouped bars per die → **Solo / Healer / Full Party** (legend).
* **Y-axis:** metric value.
* **Title:** `"{metric} - {monster}"`.

#### Cross-monster plots (in `graphs/_ALL_MONSTERS/`)

* **One PNG per (metric, team)** (e.g., `final_baseline_P_win_solo_all_monsters.png`).
* **X-axis:** monster.
* **Bars:** one color per **die**; for each monster the bars are offset by die, with a legend showing die labels.

> Colors are consistent per die across all-monster charts, and the legend lists **all** dice.

## Code Overview

### Tunables & Stat Blocks

* `N_SIMS`, `DICE_TO_TEST`, `RANDOM_SEED` — defaults used unless overridden by CLI.
* Party:

  * `WARRIOR` + abilities: `SECOND_WIND_THRESHOLD`, `ACTION_SURGE_USES`, `SUPERIORITY_*`, `POWER_ATTACK`.
  * `HEALER` + `HEALER_SLOTS_L10` and `heal_amount(...)`.
  * `ROGUE` (Sneak Attack, Steady Aim, Uncanny Dodge).
  * `WIZARD` (slots, cantrip scaling, Shield logic).
* Monsters (`MONSTERS` dict): HP/AC/attack profile plus traits like `REGEN`, `BREATH`, `COUNTER_ON_MISS`, `SPELL_RESIST_AC_BONUS`, `AUTO_SPELL_RESIST_PCT`, `WOLF`, etc.

### Helpers

* Dice & attacks: `roll`, `roll_attack`, `roll_attack_adv`, `dmg`.
* Targeting & AC: `monster_effective_ac`.
* Turn order: `initiative_order`.
* Recharge & AoE: `try_breath` applies per-target saves and optional multi-charge spend.
* Crit-streak tracking: `end_streak_if_any`.
* Conditional probability utility: `conditional_prob`.

### Battle Simulators

* `simulate_battle_1v1(w_die, monster)`
  Warrior vs Monster; models Action Surge timing, Battlemaster dice, power attack toggle when advantaged, monster regen/breath/wolf, and a simple “counter on miss” (Marauder).
* `simulate_battle_with_healer(w_die, monster)`
  Adds a healer that chooses between damage and a simple triage strategy (`healing_word`, `cure_wounds`, `mass_healing_word`) based on party HP & slot availability.
* `simulate_battle_full_party(w_die, monster)`
  Full party: adds Rogue (Sneak Attack + Steady Aim + Uncanny Dodge) and Wizard (slot management, Magic Missile vs Chromatic Orb vs Fire Bolt; Shield reactions). Monster AOE, regen, wolves, counters, and targeting heuristics included.

Each simulator returns flags for win/initiative/first-turn events and crit-streak data used by…

### Aggregation & I/O

* `summarize_many(sim_fn, w_die, monster, n_sims)`
  Runs many fights and computes the CSV row for that die.
* `write_csv(path, rows)`
  Writes a CSV to `csv/<MONSTER>/...` (dirs auto-created).
* Directory helpers (`monster_csv_dir`, `monster_graph_dir`, `all_monsters_graph_dir`) keep outputs organized.

### Plotting

* `_numeric_metrics(rows)` — discovers which keys are numeric and should be plotted.
* `_ensure_same_dice(rows)` — derives die labels (`d4…d20`) in order.
* `plot_per_monster(monster_key, rows_solo, rows_heal, rows_full)`
  Grouped bars per die for Solo/Healer/Full.
* `plot_all_monsters(results_by_monster)`
  For each metric & team, draws bars per monster **colored by die**, with a single legend of die labels. Colors are stable across monsters.

### Entrypoints

* `parse_args()` — CLI options.
* `run_suite_for_monster(monster_key, n_sims)` — runs all three scenarios for one monster, writes CSVs & per-monster plots, returns data for final plots.
* `main()` — single-monster mode by default; `--all-monsters` runs everything and then produces the cross-monster charts.
* `get_monster(name)` — resolves keys/aliases.

## Tips & Troubleshooting

* **Reproducibility:** use `--seed` (default `42`); higher `--sims` smooths variance.
* **Matplotlib labels cut off?** Images use `fig.tight_layout()`, but if you enlarge fonts globally, consider increasing `figsize` or DPI.
* **Extend with new monsters:** add a dict in `MONSTERS` + any traits; the rest of the pipeline (CSV & plots) updates automatically.
* **Change dice tested:** edit `DICE_TO_TEST`.

---

Happy sim-slaying! 🐉🎲