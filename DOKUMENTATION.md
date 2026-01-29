# Dokumentation (SLAM + evo)

## 1) Ziel
Das Projekt fuehrt viele SLAM-Laeufe mit unterschiedlichen Parametern aus,
wertet jeden Lauf mit **echtem evo** aus und sammelt die Ergebnisse in einer Uebersicht.

Wichtig:
- `dummy_slam.py` ist ein **Platzhalter** (Demo-SLAM).
- Die Auswertung ist **echt**: `evo_ape` und `evo_rpe` werden aufgerufen.

## 2) Voraussetzungen
- Python 3
- evo (stellt `evo_ape` und `evo_rpe` bereit)

Optional, falls evo nicht im PATH gefunden wird:
- `EVO_BIN_DIR=/pfad/zur/venv/bin`

## 3) Schnellstart
Im Projektordner:
```
python3 runner.py
```
Wenn evo nicht gefunden wird:
```
export EVO_BIN_DIR=/Users/janh/.venv/bin
python3 runner.py
```

## 4) Komponenten (Dateien) und Aufgaben
- `runner.py`
  - Startet alle Runs (Grid Search)
  - Schreibt `runs/grid_summary.csv` und `runs/best_result.txt`
  - Loggt pro Run in `runs/<run_id>/run.log`

- `generate_config_ini.py`
  - Baut `config.ini` aus `slam_template.ini` und Parametern
  - Aufruf:
    - `python3 generate_config_ini.py <run_id> KEY=VALUE ...`

- `dummy_slam.py`
  - Erzeugt Demo-Trajektorien im **TUM-Format**
  - Schreibt `trajectory_est.tum` (Schaetzung) und `trajectory_gt.tum` (Ground-Truth)

- `evo_runner.py`
  - Ruft `evo_ape` und `evo_rpe` auf
  - Schreibt `metrics.json`

- `analyze_results.py`
  - Liest `runs/grid_summary.csv`
  - Gibt Basisstatistiken und beste Runs aus

## 5) Datenfluss pro Run
1) `runner.py` waehlt eine Parameterkombination aus `GRID`.
2) `generate_config_ini.py` schreibt `runs/<run_id>/config.ini`.
3) `dummy_slam.py` schreibt:
   - `runs/<run_id>/trajectory_est.tum`
   - `runs/<run_id>/trajectory_gt.tum`
4) `evo_runner.py` startet `evo_ape` und `evo_rpe`.
5) `metrics.json` wird geschrieben, der Run wird in der Uebersicht erfasst.

## 6) Parameter und Konfiguration
### 6.1 GRID (in `runner.py`)
Beispiel:
```
GRID = {
    "MAX_FEATURES": [600, 800, 1000],
    "LOOP_CLOSURE": [True],
    "MAP_RESOLUTION": [0.05, 0.1, 0.00001]
}
```
Bedeutung:
- Die Keys sind Parameter, die im Template ersetzt werden.
- Die Werte sind alle Varianten, die getestet werden.
- Jede Kombination ergibt einen Run.

### 6.2 slam_template.ini (Platzhalter)
In der Vorlage muessen Platzhalter stehen wie:
```
MAX_FEATURES={{MAX_FEATURES}}
LOOP_CLOSURE={{LOOP_CLOSURE}}
MAP_RESOLUTION={{MAP_RESOLUTION}}
```
Diese werden von `generate_config_ini.py` ersetzt.

## 7) Dateiformate (genau definiert)
### 7.1 TUM-Trajektorie
Format pro Zeile:
```
<timestamp> <tx> <ty> <tz> <qx> <qy> <qz> <qw>
```
- `trajectory_est.tum` = Schaetzung
- `trajectory_gt.tum`  = Ground-Truth

### 7.2 metrics.json
Beispiel:
```
{
  "ape_mean": 0.012,
  "rpe_mean": 0.017,
  "ape_rmse": 0.024,
  "rpe_rmse": 0.028,
  "runtime_sec": 0.38,
  "success": true,
  "source": "evo_cli"
}
```
Bedeutung:
- `ape_mean`: mittlerer APE (Translation)
- `rpe_mean`: mittlerer RPE (Translation)
- `ape_rmse`, `rpe_rmse`: RMSE aus evo
- `runtime_sec`: Zeit fuer die Auswertung
- `source`: "evo_cli" (echte evo-CLI)

## 8) Ordnerstruktur
- `runs/<run_id>/config.ini`
- `runs/<run_id>/trajectory_est.tum`
- `runs/<run_id>/trajectory_gt.tum`
- `runs/<run_id>/metrics.json`
- `runs/<run_id>/evo_ape_results.zip`
- `runs/<run_id>/evo_rpe_results.zip`
- `runs/<run_id>/status.txt`
- `runs/<run_id>/run.log`
- `runs/grid_summary.csv`
- `runs/best_result.txt`

## 9) Statuswerte (status.txt)
- `SUCCESS`       -> Run OK, metrics.json vorhanden
- `FAILED`        -> Ein Schritt ist fehlgeschlagen
- `FAILED_METRICS`-> evo lief, aber keine Metriken gefunden
- `TIMEOUT`       -> Schritt hat zu lange gedauert

## 10) Logs
- `runs/<run_id>/run.log` wird **pro Run neu geschrieben**.
- Das Log enthaelt die ausgefuehrten Kommandos und deren Ausgaben.

## 11) Analyse der Ergebnisse
```
python3 analyze_results.py
```
Ausgabe:
- Beste Runs nach APE
- Basisstatistiken (min/max/mean/median)

Optional:
```
python3 analyze_results.py --save runs/analysis.txt
```

## 12) Typische Fehler und Loesungen
- evo wird nicht gefunden:
  - `export EVO_BIN_DIR=/Users/janh/.venv/bin`
- Ground-Truth fehlt:
  - `trajectory_gt.tum` muss im Run-Ordner liegen
- Keine Metriken:
  - `status.txt` zeigt `FAILED_METRICS`
  - `run.log` enthaelt den Fehlergrund

## 13) Ausblick (optional)
Moegliche Erweiterungen:
- Echte SLAM-Anbindung statt Dummy
- Weitere Suchstrategien
- Plots/Visualisierung
