"""Wrapper fuer evo-Auswertung (Dummy oder echte evo-CLI).

Kurzfassung fuer Nicht-Programmierer:
- Dieses Skript entscheidet, wie die Auswertung laeuft.
- Im Dummy-Modus ruft es das einfache `evo.py` auf.
- Im Evo-Modus ruft es `evo_ape`/`evo_rpe` direkt auf (TUM-Format).
- Im External-Modus ruft es eine eigene evo-CLI auf, die du vorgibst.
- Die Ergebnisse landen standardisiert in `metrics.json`.

Beispiele:
  Dummy (automatisch, wenn evo_ape nicht gefunden wird):
    python evo_runner.py runs/run_01/trajectory_est.tum

  Evo (automatisch, wenn evo_ape vorhanden ist):
    python evo_runner.py runs/run_01/trajectory_est.tum

  External mit eigener CLI (Template mit Platzhaltern):
    python evo_runner.py runs/run_01/trajectory.txt \
      --ground-truth data/gt.txt \
      --mode external \
      --cmd "evo_ape tum {gt} {est} --save_results {metrics}"

Platzhalter im --cmd:
  {est}     = Pfad zur Schaetzung (Trajectory)
  {gt}      = Pfad zur Ground-Truth (optional)
  {metrics} = Pfad zur metrics.json
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import zipfile


def parse_args():
    parser = argparse.ArgumentParser(description="Evo-Wrapper")
    parser.add_argument("trajectory", help="Pfad zur Trajektorie (Schaetzung)")
    parser.add_argument("--ground-truth", dest="ground_truth", default=None)
    parser.add_argument("--mode", choices=["auto", "dummy", "external", "evo"], default="auto")
    parser.add_argument("--cmd", default=None, help="Externe evo-CLI als Template-String")
    parser.add_argument("--metrics-path", default=None)
    return parser.parse_args()


def read_metrics_txt(path):
    ape = None
    rpe = None
    if not os.path.isfile(path):
        return None, None
    with open(path, "r") as f:
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


def write_metrics_json(path, ape, rpe, runtime_sec, source, ape_rmse=None, rpe_rmse=None):
    payload = {
        "ape_mean": ape,
        "rpe_mean": rpe,
        "ape_rmse": ape_rmse,
        "rpe_rmse": rpe_rmse,
        "runtime_sec": runtime_sec,
        "success": ape is not None or rpe is not None,
        "source": source,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def run_dummy(trajectory_path, metrics_path):
    start = time.time()
    subprocess.run([sys.executable, "evo.py", trajectory_path], check=True)
    runtime_sec = time.time() - start

    run_dir = os.path.dirname(trajectory_path)
    metrics_txt = os.path.join(run_dir, "metrics.txt")
    ape, rpe = read_metrics_txt(metrics_txt)
    write_metrics_json(metrics_path, ape, rpe, runtime_sec, source="dummy")


def find_ground_truth(run_dir):
    candidates = [
        os.path.join(run_dir, "trajectory_gt.tum"),
        os.path.join(run_dir, "groundtruth.tum"),
        os.path.join(run_dir, "gt.tum"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def find_evo_cmd(name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_dir = os.environ.get("EVO_BIN_DIR")
    candidates = [
        env_dir,
        os.path.join(base_dir, ".venv", "bin"),
        os.path.join(os.path.expanduser("~"), ".venv", "bin"),
    ]
    candidates = [c for c in candidates if c]
    search_path = os.pathsep.join(candidates + [os.environ.get("PATH", "")])
    return shutil.which(name, path=search_path)


def read_stats_from_zip(zip_path):
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Ergebnis-ZIP fehlt: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        if "stats.json" not in zf.namelist():
            raise FileNotFoundError("stats.json fehlt im Ergebnis-ZIP")
        return json.loads(zf.read("stats.json"))


def run_evo_cli(trajectory_path, ground_truth, metrics_path):
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

    start = time.time()
    print(f"Evo-CLI: {evo_ape} / {evo_rpe}")
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
        source="evo_cli",
    )


def run_external(cmd_template, trajectory_path, ground_truth, metrics_path):
    if "{gt}" in cmd_template and not ground_truth:
        raise ValueError("--ground-truth fehlt, aber {gt} wird im --cmd verwendet")
    if not cmd_template.strip():
        raise ValueError("--cmd ist leer")

    cmd_text = cmd_template.format(est=trajectory_path, gt=ground_truth or "", metrics=metrics_path)
    cmd = shlex.split(cmd_text)
    if not cmd:
        raise ValueError("Konnte Kommando nicht parsen")

    start = time.time()
    subprocess.run(cmd, check=True)
    runtime_sec = time.time() - start

    if not os.path.isfile(metrics_path):
        raise FileNotFoundError("metrics.json fehlt nach externem Lauf")

    # Optional: runtime_sec in metrics.json nachtragen.
    try:
        with open(metrics_path, "r") as f:
            data = json.load(f)
        data["runtime_sec"] = runtime_sec
        data.setdefault("source", "external")
        with open(metrics_path, "w") as f:
            json.dump(data, f, indent=2)
    except (OSError, ValueError, json.JSONDecodeError):
        # Wenn das Format unbekannt ist, nicht ueberschreiben.
        pass


def main():
    args = parse_args()

    trajectory_path = args.trajectory
    if not os.path.isfile(trajectory_path):
        print(f"FEHLER: Trajektorie nicht gefunden: {trajectory_path}")
        return 2

    run_dir = os.path.dirname(trajectory_path)
    metrics_path = args.metrics_path or os.path.join(run_dir, "metrics.json")

    mode = args.mode
    if mode == "auto":
        if args.cmd:
            mode = "external"
        elif find_evo_cmd("evo_ape") and find_evo_cmd("evo_rpe"):
            mode = "evo"
        else:
            mode = "dummy"

    try:
        print(f"Evo-Wrapper mode: {mode}")
        if mode == "dummy":
            run_dummy(trajectory_path, metrics_path)
        elif mode == "evo":
            run_evo_cli(trajectory_path, args.ground_truth, metrics_path)
        else:
            if not args.cmd:
                raise ValueError("External mode braucht --cmd")
            run_external(args.cmd, trajectory_path, args.ground_truth, metrics_path)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as exc:
        print(f"FEHLER: {exc}")
        return 2

    print(f"Evo-Wrapper OK -> metrics.json: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
