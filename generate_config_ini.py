"""Erzeugt eine konkrete config.ini aus einer Vorlage und Parametern.

Kurzfassung fuer Nicht-Programmierer:
- Es gibt eine Vorlage (slam_template.ini) mit Platzhaltern wie {{MAX_FEATURES}}.
- Diese werden durch echte Werte ersetzt.
- Die fertige config.ini landet im jeweiligen run-Ordner.

Aufruf:
  python3 generate_config_ini.py <run_id> KEY=VALUE KEY=VALUE ...

Beispiel:
  python3 generate_config_ini.py run_01 MAX_FEATURES=800 LOOP_CLOSURE=True
"""

import os
import sys

# Standardwerte, falls keine Ueberschreibungen kommen.
# Standardwerte, falls keine Ueberschreibungen kommen.
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
    """Versucht Strings in echte Datentypen umzuwandeln (bool/int/float)."""
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
    """Ueberschreibt Parameter aus der Kommandozeile (KEY=VALUE)."""
    for arg in args:
        if "=" not in arg:
            continue
        key, raw = arg.split("=", 1)
        if key in param_map:
            param_map[key] = coerce_value(raw)


# Kommandozeilen-Parameter in die Defaults uebernehmen.
apply_overrides(params, sys.argv[2:])

if not os.path.isfile(TEMPLATE_PATH):
    print(f"FEHLER: Template nicht gefunden: {TEMPLATE_PATH}")
    sys.exit(2)

with open(TEMPLATE_PATH, "r") as f:
    template_text = f.read()

# Platzhalter {{KEY}} durch die aktuellen Werte ersetzen.
for key, value in params.items():
    template_text = template_text.replace(f"{{{{{key}}}}}", str(value))

with open(OUTPUT_CONFIG, "w") as f:
    f.write(template_text)

print("Config erstellt")
