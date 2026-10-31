"""Schreibt daten/posts.json in die Zeile `const RAW = [...]` von index.html
und setzt das Datum „Zuletzt aktualisiert“ unter der Überschrift.

Aufruf:  python scripts/build.py daten/posts.json index.html

Das Datum ändert sich nur, wenn wirklich neue Zahlen dazugekommen sind –
eine reine Layout-Änderung lässt es stehen.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAW_ZEILE = re.compile(r"^(\s*const RAW = )(.*);$", re.M)
DATUM = re.compile(r'(<time id="aktualisiert" datetime=")[^"]*(">)[^<]*(</time>)')


def main(daten, seite):
    posts = json.loads(Path(daten).read_text(encoding="utf-8"))
    html = Path(seite).read_text(encoding="utf-8")
    json_text = json.dumps(posts, ensure_ascii=False, separators=(",", ":"))

    alt = RAW_ZEILE.search(html)
    if not alt:
        sys.exit("Zeile 'const RAW = ...;' nicht in der Seite gefunden")
    neue_zahlen = alt.group(2) != json_text
    html = html[:alt.start(2)] + json_text + html[alt.end(2):]

    if neue_zahlen:
        jetzt = datetime.now(ZoneInfo("Europe/Berlin"))
        anzeige = jetzt.strftime("%d.%m.%Y, %H:%M Uhr")
        html, gefunden = DATUM.subn(
            lambda m: m.group(1) + jetzt.isoformat(timespec="minutes") + m.group(2) + anzeige + m.group(3),
            html, count=1)
        if not gefunden:
            print('Hinweis: <time id="aktualisiert"> fehlt in der Seite, Datum nicht gesetzt')
        else:
            print(f"Zuletzt aktualisiert: {anzeige}")

    Path(seite).write_text(html, encoding="utf-8")
    print(f"{len(posts)} Posts in {seite} geschrieben" + ("" if neue_zahlen else " (keine neuen Zahlen)"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
