import math
import os
import sys

if len(sys.argv) < 2:
    print("FEHLER: Kein Trajektorienpfad übergeben")
    sys.exit(2)

trajectory_path = sys.argv[1]

if not os.path.exists(trajectory_path):
    print(f"FEHLER: Trajektorie nicht gefunden: {trajectory_path}")
    sys.exit(2)

run_dir = os.path.dirname(trajectory_path)

points = []
with open(trajectory_path, "r") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) < 3:
            continue
        try:
            x = float(parts[1])
            y = float(parts[2])
        except ValueError:
            continue
        points.append((x, y))

if not points:
    print("FEHLER: Keine gueltigen Punkte in der Trajektorie gefunden")
    sys.exit(2)

ape_val = sum(math.hypot(x, y) for x, y in points) / len(points)

if len(points) >= 2:
    step_sum = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        step_sum += math.hypot(x2 - x1, y2 - y1)
    rpe_val = step_sum / (len(points) - 1)
else:
    rpe_val = 0.0

ape = round(ape_val, 3)
rpe = round(rpe_val, 3)

metrics_path = os.path.join(run_dir, "metrics.txt")
with open(metrics_path, "w") as f:
    f.write(f"APE: {ape}\n")
    f.write(f"RPE: {rpe}\n")

print(f"Evo OK → APE={ape}, RPE={rpe}")
