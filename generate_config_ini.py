import os
import sys

params = {
    "MAX_FEATURES": 800,
    "LOOP_CLOSURE": True,
    "MAP_RESOLUTION": 0.005
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "slam_template.ini")
RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "run_001"
OUTPUT_DIR = os.path.join(BASE_DIR, "runs", RUN_ID)
OUTPUT_CONFIG = os.path.join(OUTPUT_DIR, "config.ini")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def coerce_value(raw):
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def apply_overrides(param_map, args):
    for arg in args:
        if "=" not in arg:
            continue
        key, raw = arg.split("=", 1)
        if key in param_map:
            param_map[key] = coerce_value(raw)


apply_overrides(params, sys.argv[2:])

if not os.path.isfile(TEMPLATE_PATH):
    print(f"FEHLER: Template nicht gefunden: {TEMPLATE_PATH}")
    sys.exit(2)

with open(TEMPLATE_PATH, "r") as f:
    template_text = f.read()

for key, value in params.items():
    template_text = template_text.replace(f"{{{{{key}}}}}", str(value))

with open(OUTPUT_CONFIG, "w") as f:
    f.write(template_text)

print("Config erstellt")
