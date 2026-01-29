"""Einfache Auswertung der Ergebnis-CSV aus den Runs.

Kurzfassung fuer Nicht-Programmierer:
- Liest `runs/grid_summary.csv`.
- Filtert nur Runs mit Status SUCCESS.
- Gibt Basisstatistiken fuer APE/RPE aus.
- Zeigt die besten Runs nach APE.
"""

import argparse
import csv
import os
import statistics


def parse_args():
    parser = argparse.ArgumentParser(description="Analyse der Runs")
    parser.add_argument("--summary", default=os.path.join("runs", "grid_summary.csv"))
    parser.add_argument("--top", type=int, default=5, help="Top-N Runs ausgeben")
    parser.add_argument("--save", default=None, help="Optionaler Pfad fuer Report-Datei")
    return parser.parse_args()


def to_float(value):
    # Wandelt CSV-Strings sicher in Float um.
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def describe(values):
    # Kurze Statistik (nur wenn Werte vorhanden sind).
    if not values:
        return None
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
    }


def main():
    args = parse_args()
    summary_path = args.summary

    if not os.path.isfile(summary_path):
        print(f"FEHLER: Datei nicht gefunden: {summary_path}")
        return 2

    rows = []
    with open(summary_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["ape"] = to_float(row.get("ape"))
            row["rpe"] = to_float(row.get("rpe"))
            rows.append(row)

    if not rows:
        print("FEHLER: Keine Daten in der CSV")
        return 2

    # Filter nur erfolgreiche Runs
    ok_rows = [r for r in rows if r.get("status") == "SUCCESS"]

    # Werte fuer Statistik sammeln (nur vorhandene Zahlen).
    ape_vals = [r["ape"] for r in ok_rows if r["ape"] is not None]
    rpe_vals = [r["rpe"] for r in ok_rows if r["rpe"] is not None]

    best_by_ape = None
    if ape_vals:
        best_by_ape = min(ok_rows, key=lambda r: r["ape"] if r["ape"] is not None else float("inf"))

    best_by_rpe = None
    if rpe_vals:
        best_by_rpe = min(ok_rows, key=lambda r: r["rpe"] if r["rpe"] is not None else float("inf"))

    # Text-Report vorbereiten (als Liste von Zeilen).
    lines = []
    lines.append(f"Datei: {summary_path}")
    lines.append(f"Runs total: {len(rows)} | SUCCESS: {len(ok_rows)}")

    if best_by_ape:
        lines.append(f"Bester APE: {best_by_ape['run_id']} (APE={best_by_ape['ape']})")
    if best_by_rpe:
        lines.append(f"Bester RPE: {best_by_rpe['run_id']} (RPE={best_by_rpe['rpe']})")

    stats_ape = describe(ape_vals)
    stats_rpe = describe(rpe_vals)
    if stats_ape:
        lines.append(
            "APE: "
            + f"min={stats_ape['min']}, max={stats_ape['max']}, "
            + f"mean={stats_ape['mean']:.4f}, median={stats_ape['median']:.4f}"
        )
    if stats_rpe:
        lines.append(
            "RPE: "
            + f"min={stats_rpe['min']}, max={stats_rpe['max']}, "
            + f"mean={stats_rpe['mean']:.4f}, median={stats_rpe['median']:.4f}"
        )

    if args.top > 0:
        top_rows = sorted(
            [r for r in ok_rows if r["ape"] is not None], key=lambda r: r["ape"]
        )[: args.top]
        lines.append("Top nach APE:")
        for r in top_rows:
            lines.append(f"  - {r['run_id']}: APE={r['ape']}, RPE={r['rpe']}")

    report = "\n".join(lines)
    print(report)

    if args.save:
        with open(args.save, "w") as f:
            f.write(report + "\n")
        print(f"Report gespeichert: {args.save}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
