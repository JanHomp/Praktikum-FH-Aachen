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

time.sleep(2)

trajectory_path = os.path.join(run_dir, "trajectory.txt")
with open(trajectory_path, "w") as f:
    for t in range(10):
        x = random.random()
        y = random.random()
        f.write(f"{t} {x} {y}\n")

print("Dummy-SLAM beendet")
