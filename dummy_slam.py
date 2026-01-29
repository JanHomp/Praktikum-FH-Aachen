"""Platzhalter fuer einen echten SLAM-Lauf.

Kurzfassung fuer Nicht-Programmierer:
- Liest die Konfiguration (hier nur Pfad-Check).
- Wartet kurz, um Rechenzeit zu simulieren.
- Schreibt Beispiel-Trajektorien im TUM-Format:
  - trajectory_gt.tum  (Ground Truth)
  - trajectory_est.tum (Schaetzung, leicht verrauscht)
"""

import os
import random
import sys
import time

if len(sys.argv) < 2:
    print("FEHLER: Kein Config-Pfad übergeben")
    sys.exit(2)

config_path = sys.argv[1]
if not os.path.isfile(config_path):
    print(f"FEHLER: Config nicht gefunden: {config_path}")
    sys.exit(2)

run_dir = os.path.dirname(config_path)

print(f"Dummy-SLAM gestartet mit {config_path}")

# Simulierte Rechenzeit.
time.sleep(2)

trajectory_txt = os.path.join(run_dir, "trajectory.txt")
trajectory_gt = os.path.join(run_dir, "trajectory_gt.tum")
trajectory_est = os.path.join(run_dir, "trajectory_est.tum")

# Altes Textformat (einfach) weiterhin schreiben, damit nichts bricht.
with open(trajectory_txt, "w") as f:
    for t in range(10):
        x = random.random()
        y = random.random()
        f.write(f"{t} {x} {y}\n")

# TUM-Format: timestamp tx ty tz qx qy qz qw
with open(trajectory_gt, "w") as gt, open(trajectory_est, "w") as est:
    for t in range(10):
        ts = float(t)
        x = t * 0.5
        y = 0.0
        z = 0.0
        qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
        gt.write(f"{ts} {x} {y} {z} {qx} {qy} {qz} {qw}\n")

        noise = random.gauss(0.0, 0.02)
        est.write(f"{ts} {x + noise} {y + noise} {z} {qx} {qy} {qz} {qw}\n")

print("Dummy-SLAM beendet")
