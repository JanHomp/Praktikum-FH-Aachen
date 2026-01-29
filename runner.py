"""Steuert eine Reihe von SLAM-Experimenten und sammelt Ergebnisse.

Kurzfassung fuer Nicht-Programmierer:
- Alle Parameter-Kombinationen aus GRID werden ausprobiert (Grid Search).
- Fuer jeden Versuch wird eine Konfiguration erzeugt, ein SLAM-Lauf gestartet
  und danach mit evo ausgewertet.
- Ergebnisse landen pro Lauf in einem Ordner unter runs/ und in einer CSV-Uebersicht.

Wichtige Dateien, die dieser Runner schreibt:
- runs/<run_id>/run.log           (Konsolen-Ausgaben pro Schritt)
- runs/<run_id>/metrics.json      (APE/RPE von evo)
- runs/grid_summary.csv           (Uebersicht ueber alle Runs)
- runs/best_result.txt            (bester Lauf)

Run-ID Format:
- run_XX__mf600_lc1_mr0p05
- run_XX = fortlaufende Nummer
- mf/lc/mr = kurze Codes fuer Parameter (siehe param_code)
"""

import itertools
import json
import os
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


# Parameterraum fuer die Suche.
# Hier definieren wir alle Werte, die ausprobiert werden.
# Jede Kombination aus allen Listen wird getestet (vollstaendiges Grid).
GRID = {
    "MAX_FEATURES": [600, 800, 1000],
    "LOOP_CLOSURE": [True],
    "MAP_RESOLUTION": [0.05, 0.1, 0.00001]
}

# Statuswerte (werden in status.txt geschrieben):
# - SUCCESS        : Run und Auswertung ok
# - FAILED         : Ein Schritt ist fehlgeschlagen
# - FAILED_METRICS : Auswertung lief, aber keine Metriken gefunden
# - TIMEOUT        : Ein Schritt hat zu lange gedauert


def run_step(args, log_path, timeout_seconds):
    """Fuehrt einen Einzelschritt aus und schreibt Ausgabe ins Log.

    args: Kommandozeile als Liste, z.B. ["python", "script.py", "arg1"]
    log_path: Datei, in die stdout/stderr geschrieben wird
    timeout_seconds: Abbruchzeit, falls ein Schritt haengt
    """
    # Alles, was das Subprogramm ausgibt, landet im Log.
    with open(log_path, "a") as log:
        log.write(f"\n# CMD: {' '.join(args)}\n")
        try:
            # check=True -> wir bekommen bei Fehlern eine Exception.
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


def init_run_log(log_path, run_id, params):
    """Legt ein frisches Log pro Run an (alte Inhalte werden ueberschrieben).

    Der Header hilft, alte Logdateien eindeutig einem Run zuzuordnen.
    """
    # Neues Log pro Run (alte Inhalte entfernen).
    with open(log_path, "w") as log:
        log.write(f"# RUN_ID: {run_id}\n")
        log.write("# PARAMS: " + ", ".join(f"{k}={format_value(v)}" for k, v in params.items()) + "\n")


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
    """Liest APE/RPE aus metrics.json.

    Erwartete Felder in metrics.json:
    - ape_mean, rpe_mean (float)
    """
    # Erwartet: metrics.json wird von evo_runner.py erzeugt.
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
    # Wenn nichts gelesen werden konnte, geben wir None zurueck.
    return None, None


# Reihenfolge der Parameter beibehalten (wichtig fuer CSV und Run-IDs).
param_names = list(GRID.keys())
value_sets = [GRID[name] for name in param_names]

# Alle Kombinationen aller Parameter erzeugen (vollstaendiger Grid Search).
combos = list(itertools.product(*value_sets))

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
for run_index, combo in enumerate(combos, 1):
    params = dict(zip(param_names, combo))
    run_id = build_run_id(run_index, params, param_names)
    run_dir = os.path.join(RUNS_DIR, run_id)
    config_path = os.path.join(run_dir, "config.ini")
    # Evo nutzt TUM-Format (Schaetzung).
    trajectory_path = os.path.join(run_dir, "trajectory_est.tum")
    # Parameter fuer generate_config_ini.py vorbereiten.
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
    init_run_log(log_path, run_id, params)

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

    # 3) Auswertung mit evo (echte evo-CLI)
    status = run_step([PYTHON, "evo_runner.py", trajectory_path], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    # 4) Metriken lesen und in die Uebersicht schreiben.
    ape, rpe = read_metrics(run_dir)
    if ape is None and rpe is None:
        write_status(run_dir, "FAILED_METRICS")
        rows.append({"run_id": run_id, "params": params, "status": "FAILED_METRICS", "ape": ape, "rpe": rpe})
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
    print(f"=== {run_id} abgeschlossen ===", flush=True)

# CSV-Zusammenfassung schreiben.
# Spalten: run_id, Parameter, status, ape, rpe, best(1/leer).
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