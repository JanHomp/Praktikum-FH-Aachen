import itertools
import os
import random
import subprocess
import sys

PYTHON = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(BASE_DIR, "runs")

TIMEOUT_SECONDS = 10
LOG_LIMIT_GB = 10
LOG_LIMIT_BYTES = LOG_LIMIT_GB * 1024 * 1024 * 1024
RUN_ID_WIDTH = 2


GRID = {
    "MAX_FEATURES": [600, 800, 1000, 1200, 1400, 1600],
    "LOOP_CLOSURE": [True, False],
    "MAP_RESOLUTION": [0.05, 0.1, 0.00001, 0.005, 1, 0.0000000001]
}

SEARCH_MODE = "grid"  
RANDOM_SAMPLES = 20
RANDOM_SEED = 42


def run_step(args, log_path, timeout_seconds):
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
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def slug_value(value):
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
    return {
        "MAX_FEATURES": "mf",
        "LOOP_CLOSURE": "lc",
        "MAP_RESOLUTION": "mr"
    }.get(name, name.lower())


def build_run_id(index, params, names):
    base = f"run_{index:0{RUN_ID_WIDTH}d}"
    tags = [f"{param_code(name)}{slug_value(params[name])}" for name in names]
    return base + "__" + "_".join(tags)


def get_dir_size(path):
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
    status_path = os.path.join(run_dir, "status.txt")
    with open(status_path, "w") as f:
        f.write(status + "\n")


def read_metrics(run_dir):
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


param_names = list(GRID.keys())
value_sets = [GRID[name] for name in param_names]

if SEARCH_MODE == "grid":
    combos = list(itertools.product(*value_sets))
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
else:
    print(f"FEHLER: Unbekannter SEARCH_MODE: {SEARCH_MODE}")
    sys.exit(2)

if not combos:
    print("FEHLER: Grid ist leer, keine Runs ausgefuehrt")
    sys.exit(2)

os.makedirs(RUNS_DIR, exist_ok=True)
summary_path = os.path.join(RUNS_DIR, "grid_summary.csv")
best_path = os.path.join(RUNS_DIR, "best_result.txt")
best = None
rows = []

for i, combo in enumerate(combos, 1):
    params = dict(zip(param_names, combo))
    run_id = build_run_id(i, params, param_names)
    run_dir = os.path.join(RUNS_DIR, run_id)
    config_path = os.path.join(run_dir, "config.ini")
    trajectory_path = os.path.join(run_dir, "trajectory.txt")
    overrides = [f"{k}={format_value(params[k])}" for k in param_names]
    log_path = os.path.join(run_dir, "run.log")

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

    status = run_step([PYTHON, "generate_config_ini.py", run_id, *overrides], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    status = run_step([PYTHON, "dummy_slam.py", config_path], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    status = run_step([PYTHON, "dummy_evo.py", trajectory_path], log_path, TIMEOUT_SECONDS)
    if status != "OK":
        write_status(run_dir, status)
        rows.append({"run_id": run_id, "params": params, "status": status, "ape": None, "rpe": None})
        continue

    write_status(run_dir, "SUCCESS")
    ape, rpe = read_metrics(run_dir)
    rows.append({"run_id": run_id, "params": params, "status": "SUCCESS", "ape": ape, "rpe": rpe})

    if ape is not None:
        if best is None or ape < best["ape"] or (ape == best["ape"] and rpe is not None and rpe < best["rpe"]):
            best = {
                "run_id": run_id,
                "params": params,
                "ape": ape,
                "rpe": rpe
            }

    print(f"=== {run_id} abgeschlossen ===", flush=True)

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
