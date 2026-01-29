# Dokumentation und Plan (SLAM + evo)

## 1) Kontext und Ziel
Dieses Projekt fuehrt viele SLAM-Laeufe mit unterschiedlichen Parametern aus,
wertet jeden Lauf aus und sammelt die Ergebnisse in einer Uebersicht.
Aktuell sind SLAM und evo als Dummy-Skripte umgesetzt, um den Ablauf zu testen.

Ziele dieser Doku:
- Aktuellen Ist-Stand und Datenfluss festhalten.
- Saubere Ingenieur-Dokumentation und Planungsstruktur skizzieren.
- Planung fuer echte evo-Integration, Auswertung und intelligente Steuerung der Suche.

## 2) Ist-Stand (Ablauf und Dateien)
### Skripte
- `runner.py`: Orchestrator, startet jeden Lauf und sammelt Ergebnisse.
- `generate_config_ini.py`: Erzeugt `config.ini` aus `slam_template.ini`.
- `dummy_slam.py`: Simuliert SLAM und schreibt `trajectory.txt`.
- `evo.py`: Dummy-Auswertung, schreibt `metrics.txt`.
- `evo_runner.py`: Wrapper fuer Dummy oder echte evo-CLI, schreibt `metrics.json`.
- `analyze_results.py`: Liest die Uebersicht und macht Basis-Analysen.

### Datenfluss pro Lauf (aktuell)
1) `runner.py` waehlt Parameter (Grid/Random/Bandit).
2) `generate_config_ini.py` schreibt `runs/<run_id>/config.ini`.
3) `dummy_slam.py` schreibt `trajectory_est.tum` + `trajectory_gt.tum`.
4) `evo_runner.py` ruft evo_ape/evo_rpe (oder Dummy) und schreibt `metrics.json`.
5) `runner.py` schreibt Status + `grid_summary.csv` + `best_result.txt`.

Hinweis:
- `runner.py` zeigt jetzt pro Lauf, ob Metriken gefunden wurden (APE/RPE),
  oder eine Warnung, falls nicht.

### Ordnerstruktur
- `runs/<run_id>/config.ini`
- `runs/<run_id>/trajectory_est.tum`
- `runs/<run_id>/trajectory_gt.tum`
- `runs/<run_id>/metrics.json`
- `runs/<run_id>/status.txt`
- `runs/<run_id>/run.log`
- `runs/grid_summary.csv`
- `runs/best_result.txt`

## 3) Ingenieur-Dokumentation: Was gehoert dazu?
Empfohlene Artefakte (kurz, klar, nachverfolgbar):
1) Anforderungen (Requirements)
   - Zielmetriken (z.B. minimaler APE)
   - Rahmenbedingungen (Zeitlimit, Hardware, Datensaetze)
2) Systemuebersicht (Architecture)
   - Komponenten und Datenfluesse
   - Schnittstellen und Dateiformate
3) Experiment-Plan
   - Welche Parameter, welche Grenzen, warum diese Werte
   - Suchstrategie (Grid/Random/Bayesian)
4) Test- und Validierungsplan
   - Wie pruefen wir, dass Ergebnisse korrekt sind?
   - Welche Checks laufen automatisiert?
5) Ergebnis-Report
   - Tabellen, Kenngroessen, Visualisierungen
6) Entscheidungslog (Decision Log)
   - Warum wurde ein Parameterbereich gewaehlt?
   - Warum wurde eine Metrik priorisiert?

Dokumentationsregeln (praxisnah):
- Jede Datei hat Datum/Version und einen eindeutigen Zweck.
- Alle Annahmen sind explizit notiert.
- Ergebnisse sind reproduzierbar (Parameter + Daten + Versionen).
- Jede Kennzahl ist definiert (was genau misst sie?).

## 4) Planung (Vorgehen als Ingenieur)
Vorschlag fuer eine schlanke Planungsstruktur:
- Phase A: Anforderungs- und Datenklaerung
  - Welche Trajektorien/Datensaetze? Welche Ground-Truth?
- Phase B: Integration + Basis-Metriken
  - Echte evo-Auswertung anbinden
  - Ergebnisformat standardisieren (CSV/JSON)
- Phase C: Analyse + Reporting
  - Kennzahlen vergleichen, Ausreisser erkennen
- Phase D: Intelligente Suche
  - Adaptive Parameterwahl statt fester Grid Search

## 5) Evo-Integration (Plan)
### Ziel
Dummy-evo durch echte Auswertung ersetzen.

### Schnittstellen klaeren
- Eingang: Trajektorie im TUM-Format (timestamp tx ty tz qx qy qz qw).
- Optional: Ground-Truth-Trajektorie im gleichen Format.
- Ausgang: Metriken in standardisiertem Format (metrics.json).

### Technischer Plan (minimal)
1) Wrapper-Skript `evo_runner.py` erstellen
   - Ruft evo CLI auf (z.B. `evo_ape`, `evo_rpe`) oder Dummy.
   - Schreibt `metrics.json`.
2) `runner.py` anpassen
   - Statt `evo.py` den Wrapper starten.
   - Ergebnisse parsen und in `grid_summary.csv` uebernehmen.
3) Validierung
   - Vergleichslauf gegen bekannte Referenzdaten.

### Aktuelle Konfiguration (optional)
Standard: `evo_runner.py` nutzt automatisch `evo_ape`/`evo_rpe`, wenn sie im PATH sind
oder in `./.venv/bin` bzw. `~/.venv/bin` gefunden werden.

`runner.py` kann externe evo-Kommandos ueber Umgebungsvariablen bekommen:
- `EVO_MODE=external` oder `EVO_MODE=dummy` oder `EVO_MODE=evo`
- `EVO_CMD="... {est} ... {gt} ... {metrics} ..."`
- `EVO_GT="/pfad/zu/ground_truth.txt"`
Optional:
- `EVO_BIN_DIR="/pfad/zu/venv/bin"` (falls evo nicht im PATH liegt)

### Dateiformat-Vorschlag
- `metrics.json`:
  - `ape_mean`, `ape_rmse`, `rpe_mean`, `rpe_rmse`, `runtime_sec`, `success`.

## 6) Auswertung der Ergebnisse (Plan)
Empfohlene Analyse-Schritte:
- Basisstatistiken: Mittelwert, Median, Standardabweichung, Quantile.
- Stabilitaet: Varianz ueber mehrere Laeufe je Parametrierung.
- Nebenbedingungen: Laufzeit, Speicher, Fehlerquote.
- Visualisierungen: Scatterplots (APE vs RPE), Pareto-Front.

Ergebnisbewertung (Beispiel):
- Hauptziel: minimaler APE.
- Nebenziere: niedriger RPE, kurze Laufzeit, stabile Ergebnisse.

## 7) Intelligente Steuerung der Suche mit Live-evo
Idee: Die Suchstrategie lernt aus Zwischenergebnissen.

Moegliche Strategien:
1) Early Stopping
   - Wenn APE/RPE nach Teilstrecke klar zu schlecht ist, Lauf abbrechen.
2) Successive Halving / Hyperband
   - Viele Konfigurationen kurz testen, wenige gute laenger.
3) Bayesian Optimization
   - Modelliert Zusammenhang Parameter -> Metrik, waehlt naechste Punkte gezielt.
4) Multi-Armed Bandits
   - Balanciert Exploration (neue Parameter) vs Exploitation (bekannte gute).

Live-Loop (Konzept):
- Lauf starten -> Zwischenauswertung -> Score -> naechste Parameterwahl.
- Einfache Variante: Nach jedem Lauf Ranking aktualisieren und nur Top-N weiter testen.

### Implementiert: Bandit-Suche (einfacher, lernender Modus)
Im `runner.py` gibt es jetzt `SEARCH_MODE = "bandit"`:
- Nach jedem Lauf wird die APE benutzt, um Parameter-Werte zu bewerten.
- Werte, die in guten Runs vorkommen, werden wahrscheinlicher erneut gewaehlt.
- Es bleibt immer eine gewisse Zufallsrate (Exploration), damit neue Werte getestet werden.

Wichtige Parameter im Code:
- `BANDIT_MAX_RUNS`: Wie viele Runs maximal gemacht werden.
- `BANDIT_EPSILON`: Anteil reiner Zufallsauswahl (Exploration).

Kurz: Der Algorithmus lernt online, welche Parameter gut sind, und steuert damit
die naechsten Runs intelligenter als eine feste Grid-Search.

So aktivierst du den Modus:
- In `runner.py` die Zeile `SEARCH_MODE = "bandit"` setzen.
- Optional die Parameter `BANDIT_MAX_RUNS` und `BANDIT_EPSILON` anpassen.

## 8) Konkrete ToDo-Liste (naechste Schritte)
1) Echte evo-CLI anbinden (Wrapper + Ausgabeformat).
2) Analyse-Skript nutzen (`analyze_results.py`) und ggf. erweitern.
3) Entscheidung, welche Suchstrategie als Naechstes implementiert wird.
