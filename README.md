# Quarter Million Beers 🍺

Auswertung des Bier-Zählers der WhatsApp-Gruppe: https://19leon99.github.io/quartermillionbeers/

## Aktualisieren

1. WhatsApp → Gruppe → Gruppeninfo → **Chat exportieren** → **Ohne Medien**.
2. Hier im Repo **Add file → Upload files** und die exportierte Datei hochladen
   (die `.zip` vom iPhone oder die `.txt` von Android, Name egal) → **Commit changes**.
3. Fertig. Unter **Actions** läuft „Bierzähler aktualisieren“ (ca. 1 Minute):
   neue Bier-Posts werden an `daten/posts.json` angehängt, die Seite neu gebaut
   und veröffentlicht, und der Export wird wieder aus dem Repo gelöscht.

Was das Skript nicht eindeutig zuordnen konnte, steht in `daten/pruefen.md`
(und in der Zusammenfassung des Actions-Laufs).

## Von Hand korrigieren

In `daten/korrekturen.json` (wird bei jedem Lauf angewendet):

```json
[
  {"zeit": "2026-11-01T21:15", "person": "Basti", "biere_gezaehlt": "2"},
  {"zeit": "2026-11-01T21:20", "person": "Jan", "entfernen": true}
]
```

`zeit` und `person` müssen genau so geschrieben sein wie in `daten/posts.json`.

## Dateien

- `index.html` – die Website (die Daten stehen in der Zeile `const RAW = …`)
- `daten/posts.json` – alle gezählten Bier-Posts
- `scripts/update.py` – liest den Export und hängt neue Posts an
- `scripts/build.py` – schreibt `posts.json` in die Website
- `.github/workflows/update.yml` – der automatische Ablauf
