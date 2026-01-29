"""Steuert eine Reihe von SLAM-Experimenten und sammelt Ergebnisse.

Kurzfassung fuer Nicht-Programmierer:
- Es werden mehrere Parameter-Kombinationen ausprobiert (Grid/Random/Bandit).
- Fuer jeden Versuch wird eine Konfiguration erzeugt, ein SLAM-Lauf gestartet
  und danach mit evo ausgewertet.
- Ergebnisse landen pro Lauf in einem Ordner unter runs/ und in einer CSV-Uebersicht.
"""

import itertools
import json
import os
import random
import subprocess
import sys

# Pfad zum aktuell laufenden Python-Interpreter (damit Subskripte gleich laufen).
PYTHON = sys.executable
# Basisordner des Projekts (wo diese Datei liegt).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Sammelordner fuer alle Versuchslaeufe.
RUNS_DIR = os.path.join(BASE_DIR, "runs")

# Sicherheitsgrenzen: einzelne Schritte duerfen nicht zu lange laufen
# und der Log-Ordner soll nicht unendlich wachsen.
TIMEOUT_SECONDS = 10
LOG_LIMIT_GB = 10
LOG_LIMIT_BYTES = LOG_LIMIT_GB * 1024 * 1024 * 1024
RUN_ID_WIDTH = 2

# Optional: externe evo-CLI per Umgebungsvariablen steuern.
# Beispiel:
#   export EVO_MODE=external
#   export EVO_CMD="evo_ape tum {gt} {est} --save_results {metrics}"
#   export EVO_GT="/pfad/zu/ground_truth.txt"
EVO_MODE = os.environ.get("EVO_MODE")
EVO_CMD = os.environ.get("EVO_CMD")
EVO_GT = os.environ.get("EVO_GT")


# Parameterraum fuer die Suche.
# Hier definieren wir alle Werte, die ausprobiert werden.
GRID = {
    "MAX_FEATURES": [600, 800, 1000],
    "LOOP_CLOSURE": [True],
    "MAP_RESOLUTION": [0.05, 0.1, 0.00001]
}

# "grid" prueft alle Kombinationen; "random" zieht eine Stichprobe;
# "bandit" lernt waehrend des Laufens, welche Parameter gut sind.
SEARCH_MODE = "grid"
RANDOM_SAMPLES = 20
RANDOM_SEED = 42

# Bandit-Search (intelligente Steuerung mit Live-Ergebnissen).
BANDIT_MAX_RUNS = 20
BANDIT_EPSILON = 0.2
BANDIT_SCORE_EPS = 1e-6
BANDIT_SAMPLE_TRIES = 30


def run_step(args, log_path, timeout_seconds):
    """Fuehrt einen Einzelschritt aus und schreibt Ausgabe ins Log.

    args: Kommandozeile als Liste, z.B. ["python", "script.py", "arg1"]
    log_path: Datei, in die stdout/stderr geschrieben wird
    timeout_seconds: Abbruchzeit, falls ein Schritt haengt
    """
    with open(log_path, "a") as log:
        log.write(f"\n# CMD: {' '.join(args)}\n")
        try:
            subprocess.run(
                args,
                check=True,
                cwd=BASE_DIR,
                stdout=log,
                stderr=log,
                timeout=timeout_seconds
            )
            return "OK"
        except subprocess.TimeoutExpired:
            log.write(f"# TIMEOUT after {timeout_seconds}s\n")
            return "TIMEOUT"
        except subprocess.CalledProcessError as exc:
            log.write(f"# FAILED exit={exc.returncode}\n")
            return "FAILED"


def format_value(value):
    """Sorgt fuer einheitliche Schreibweise in CSV/Logs."""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def slug_value(value):
    """Macht einen Wert fuer Ordnernamen 'sicher' (nur Zeichen die Dateinamen moegen)."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:.6g}"
        return text.replace(".", "p")
    text = str(value)
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)


def param_code(name):
    """Kurze Codes fuer Parameter, damit Run-Ordner lesbarer sind."""
    return {
        "MAX_FEATURES": "mf",
        "LOOP_CLOSURE": "lc",
        "MAP_RESOLUTION": "mr"
    }.get(name, name.lower())


def build_run_id(index, params, names):
    """Erzeugt eine eindeutige, lesbare ID fuer jeden Lauf."""
    base = f"run_{index:0{RUN_ID_WIDTH}d}"
    tags = [f"{param_code(name)}{slug_value(params[name])}" for name in names]
    return base + "__" + "_".join(tags)


def get_dir_size(path):
    """Berechnet grob die Groesse eines Ordners (fuer Speicherlimit)."""
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                continue
    return total


def write_status(run_dir, status):
    """Schreibt den Status eines Laufs in eine Datei."""
    status_path = os.path.join(run_dir, "status.txt")
    with open(status_path, "w") as f:
        f.write(status + "\n")


def read_metrics(run_dir):
    """Liest APE/RPE aus metrics.json oder metrics.txt, falls vorhanden."""
    json_path = os.path.join(run_dir, "metrics.json")
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            ape = data.get("ape_mean", data.get("ape"))
            rpe = data.get("rpe_mean", data.get("rpe"))
            ape = float(ape) if ape is not None else None
            rpe = float(rpe) if rpe is not None else None
            return ape, rpe
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    metrics_path = os.path.join(run_dir, "metrics.txt")
    if not os.path.isfile(metrics_path):
        return None, None
    ape = None
    rpe = None
    with open(metrics_path, "r") as f:
        for line in f:
            if line.startswith("APE:"):
                try:
                    ape = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("RPE:"):
                try:
                    rpe = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
    return ape, rpe


# ---- Bandit-Search Hilfsfunktionen ---------------------------------------
def init_bandit_stats(names, grid):
    stats = {}
    for name in names:
        stats[name] = {value: {"score_sum": 0.0, "count": 0} for value in grid[name]}
    return stats


def choose_bandit_value(values, stats_map, epsilon):
    if random.random() < epsilon:
        return random.choice(values)
    weights = []
    for value in values:
        entry = stats_map[value]
        if entry["count"] == 0:
            weight = 1.0
        else:
            weight = max(entry["score_sum"] / entry["count"], 1e-9)
        weights.append(weight)
    if not weights or max(weights) <= 0:
        return random.choice(values)
    return random.choices(values, weights=weights, k=1)[0]


def sample_bandit_combo(names, grid, stats, remaining, epsilon, max_tries):
    for _ in range(max_tries):
        combo = tuple(choose_bandit_value(grid[name], stats[name], epsilon) for name in names)
        if combo in remaining:
            return combo
    return random.choice(tuple(remaining))


def update_bandit(stats, params, score):
    for name, value in params.items():
        entry = stats[name][value]
        entry["score_sum"] += score
        entry["count"] += 1


# Reihenfolge der Parameter beibehalten (wichtig fuer CSV und Run-IDs).
param_names = list(GRID.keys())
value_sets = [GRID[name] for name in param_names]

# Kombinationsliste aufbauen: Grid/Random sofort, Bandit spaeter.
combos = None
combo_iter = None
bandit_stats = None
remaining_combos = None
max_runs = None

if SEARCH_MODE == "grid":
    combos = list(itertools.product(*value_sets))
    combo_iter = iter(combos)
elif SEARCH_MODE == "random":
    if RANDOM_SAMPLES <= 0:
        print("FEHLER: RANDOM_SAMPLES muss > 0 sein")
        sys.exit(2)
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)
    combos = [
        tuple(random.choice(GRID[name]) for name in param_names)
        for _ in range(RANDOM_SAMPLES)
    ]
    combo_iter = iter(combos)
elif SEARCH_MODE == "bandit":
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)
    combos = list(itertools.product(*value_sets))
    bandit_stats = init_bandit_stats(param_names, GRID)
    remaining_combos = set(combos)
    max_runs = min(BANDIT_MAX_RUNS, len(combos))
else:
    print(f"FEHLER: Unbekannter SEARCH_MODE: {SEARCH_MODE}")
    sys.exit(2)

if not combos:
    print("FEHLER: Grid ist leer, keine Runs ausgefuehrt")
    sys.exit(2)

# Ergebnisdateien vorbereiten.
os.makedirs(RUNS_DIR, exist_ok=True)
summary_path = os.path.join(RUNS_DIR, "grid_summary.csv")
best_path = os.path.join(RUNS_DIR, "best_result.txt")
best = None
rows = []

# Hauptschleife: jeder Parameter-Satz = ein Lauf.
run_index = 0
while True:
    if SEARCH_MODE == "bandit":
        if not remaining_combos or run_index >= max_runs:
            break
        combo = sample_bandit_combo(
            param_names,
            GRID,
            bandit_stats,
            remaining_combos,
            BANDIT_EPSILON,
            BANDIT_SAMPLE_TRIES,
        )
        remaining_combos.remove(combo)
    else:
        try:
            combo = next(combo_iter)
        except StopIteration:
            break

    run_index += 1
    params = dict(zip(param_names, combo))
    run_id = build_run_id(run_index, params, param_names)
    run_dir = os.path.join(RUNS_DIR, run_id)
    config_path = os.path.join(run_dir, "config.ini")
    # Evo nutzt TUM-Format (Schaetzung).
    trajectory_path = os.path.join(run_dir, "trajectory_est.tum")
    overrides = [f"{k}={format_value(params[k])}" for k in param_names]
    log_path = os.path.join(run_dir, "run.log")

    # Stoppen, falls Speicherlimit erreicht.
    if get_dir_size(RUNS_DIR) > LOG_LIMIT_BYTES:
        print(f"FEHLER: Speicherlimit erreicht ({LOG_LIMIT_GB}GB). Stoppe Runs.", flush=True)
        rows.append(
            {
                "run_id": run_id,
                "params": params,
                "status": "SKIPPED_DISK_LIMIT",
                "ape": None,
                "rpe": None
            }
        )
        break

    print(f"\n=== Starte {run_id} ===", flush=True)
    os.makedirs(run_dir, exist_ok=True)

    # 1) Konfiguration bauen
    status = run_step([PYTHON, "generate_config_ini.py", run_id, *overrides], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    # 2) SLAM-Lauf (hier Dummy-Implementierung)
    status = run_step([PYTHON, "dummy_slam.py", config_path], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    # 3) Auswertung mit evo (hier Dummy-Auswertung)
    evo_args = [PYTHON, "evo_runner.py", trajectory_path]
    if EVO_MODE:
        evo_args += ["--mode", EVO_MODE]
    if EVO_CMD:
        evo_args += ["--cmd", EVO_CMD]
    if EVO_GT:
        evo_args += ["--ground-truth", EVO_GT]

    status = run_step(evo_args, log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    ape, rpe = read_metrics(run_dir)
    if ape is None and rpe is None:
        write_status(run_dir, "SUCCESS_NO_METRICS")
        rows.append({"run_id": run_id, "params": params, "status": "SUCCESS_NO_METRICS", "ape": ape, "rpe": rpe})
        print(f"Warnung: Keine Metriken gefunden. Pruefe {log_path}", flush=True)
    else:
        write_status(run_dir, "SUCCESS")
        rows.append({"run_id": run_id, "params": params, "status": "SUCCESS", "ape": ape, "rpe": rpe})
        print(f"Evo: APE={ape}, RPE={rpe}", flush=True)

    # "Besten" Lauf merken: kleinste APE, dann RPE.
    if ape is not None:
        if best is None or ape < best["ape"] or (ape == best["ape"] and rpe is not None and rpe < best["rpe"]):
            best = {
                "run_id": run_id,
                "params": params,
                "ape": ape,
                "rpe": rpe
            }
        if SEARCH_MODE == "bandit":
            score = 1.0 / (ape + BANDIT_SCORE_EPS)
            update_bandit(bandit_stats, params, score)

    print(f"=== {run_id} abgeschlossen ===", flush=True)

# CSV-Zusammenfassung schreiben.
with open(summary_path, "w") as summary:
    summary.write("run_id," + ",".join(param_names) + ",status,ape,rpe,best\n")
    for row in rows:
        is_best = "1" if best is not None and row["run_id"] == best["run_id"] else ""
        summary.write(
            row["run_id"]
            + ","
            + ",".join(format_value(row["params"][k]) for k in param_names)
            + f",{row['status']},{row['ape'] if row['ape'] is not None else ''},{row['rpe'] if row['rpe'] is not None else ''},{is_best}\n"
        )

if best is not None:
    with open(best_path, "w") as f:
        f.write(f"run_id: {best['run_id']}\n")
        f.write("params:\n")
        for name in param_names:
            f.write(f"  {name}: {format_value(best['params'][name])}\n")
        f.write(f"APE: {best['ape']}\n")
        if best["rpe"] is not None:
            f.write(f"RPE: {best['rpe']}\n")
    print(f"\nBESTE RUN: {best['run_id']} (APE={best['ape']}, RPE={best['rpe']})", flush=True)
