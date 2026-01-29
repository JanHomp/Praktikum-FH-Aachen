"""Wrapper fuer die echte evo-Auswertung (TUM-Format).

Kurzfassung fuer Nicht-Programmierer:
- Liest eine Schaetz-Trajektorie (trajectory_est.tum).
- Findet eine Ground-Truth (trajectory_gt.tum) im selben Ordner
  oder ueber --ground-truth.
- Ruft evo_ape und evo_rpe auf und schreibt metrics.json.

Voraussetzung:
- evo ist installiert und evo_ape/evo_rpe sind auffindbar.

Hinweis zur Suche nach evo_ape/evo_rpe:
- zuerst PATH
- dann ./\.venv/bin
- dann ~/.venv/bin
- optional via EVO_BIN_DIR
"""

import argparse
import json
import os
import shutil
import subprocess
import time
import zipfile


def parse_args():
    parser = argparse.ArgumentParser(description="Evo-Wrapper (TUM)")
    parser.add_argument("trajectory", help="Pfad zur Trajektorie (Schaetzung)")
    parser.add_argument("--ground-truth", dest="ground_truth", default=None)
    parser.add_argument("--metrics-path", default=None)
    return parser.parse_args()


def find_evo_cmd(name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_dir = os.environ.get("EVO_BIN_DIR")
    # Kandidaten-Reihenfolge: Projekt-venv, User-venv, PATH.
    candidates = [
        env_dir,
        os.path.join(base_dir, ".venv", "bin"),
        os.path.join(os.path.expanduser("~"), ".venv", "bin"),
    ]
    candidates = [c for c in candidates if c]
    search_path = os.pathsep.join(candidates + [os.environ.get("PATH", "")])
    return shutil.which(name, path=search_path)


def find_ground_truth(run_dir):
    # Ground-Truth suchen (gleicher Run-Ordner).
    candidates = [
        os.path.join(run_dir, "trajectory_gt.tum"),
        os.path.join(run_dir, "groundtruth.tum"),
        os.path.join(run_dir, "gt.tum"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def read_stats_from_zip(zip_path):
    # evo speichert die Metriken in stats.json im ZIP-Archiv.
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Ergebnis-ZIP fehlt: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        if "stats.json" not in zf.namelist():
            raise FileNotFoundError("stats.json fehlt im Ergebnis-ZIP")
        return json.loads(zf.read("stats.json"))


def write_metrics_json(path, ape, rpe, runtime_sec, ape_rmse, rpe_rmse):
    # Einheitliches Ergebnisformat fuer den Runner.
    payload = {
        "ape_mean": ape,
        "rpe_mean": rpe,
        "ape_rmse": ape_rmse,
        "rpe_rmse": rpe_rmse,
        "runtime_sec": runtime_sec,
        "success": True,
        "source": "evo_cli",
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def run_evo(trajectory_path, ground_truth, metrics_path):
    run_dir = os.path.dirname(trajectory_path)
    gt_path = ground_truth or find_ground_truth(run_dir)
    if not gt_path:
        raise FileNotFoundError("Ground-Truth fehlt (erwartet trajectory_gt.tum)")

    evo_ape = find_evo_cmd("evo_ape")
    evo_rpe = find_evo_cmd("evo_rpe")
    if not evo_ape or not evo_rpe:
        raise FileNotFoundError("evo_ape/evo_rpe nicht gefunden (PATH oder ~/.venv)")

    ape_zip = os.path.join(run_dir, "evo_ape_results.zip")
    rpe_zip = os.path.join(run_dir, "evo_rpe_results.zip")

    print(f"Evo-CLI: {evo_ape} / {evo_rpe}")
    start = time.time()
    subprocess.run(
        [evo_ape, "tum", gt_path, trajectory_path, "--save_results", ape_zip, "--silent"],
        check=True,
    )
    subprocess.run(
        [evo_rpe, "tum", gt_path, trajectory_path, "--save_results", rpe_zip, "--silent"],
        check=True,
    )
    runtime_sec = time.time() - start

    ape_stats = read_stats_from_zip(ape_zip)
    rpe_stats = read_stats_from_zip(rpe_zip)

    write_metrics_json(
        metrics_path,
        ape=ape_stats.get("mean"),
        rpe=rpe_stats.get("mean"),
        ape_rmse=ape_stats.get("rmse"),
        rpe_rmse=rpe_stats.get("rmse"),
        runtime_sec=runtime_sec,
    )


def main():
    args = parse_args()

    trajectory_path = args.trajectory
    if not os.path.isfile(trajectory_path):
        print(f"FEHLER: Trajektorie nicht gefunden: {trajectory_path}")
        return 2

    run_dir = os.path.dirname(trajectory_path)
    metrics_path = args.metrics_path or os.path.join(run_dir, "metrics.json")

    try:
        run_evo(trajectory_path, args.ground_truth, metrics_path)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        print(f"FEHLER: {exc}")
        return 2

    print(f"Evo-Wrapper OK -> metrics.json: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
