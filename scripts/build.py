"""Schreibt daten/posts.json in die Zeile `const RAW = [...]` von index.html.

Aufruf:  python scripts/build.py daten/posts.json index.html
"""

import json
import re
import sys
from pathlib import Path


def main(daten, seite):
    posts = json.loads(Path(daten).read_text(encoding="utf-8"))
    html = Path(seite).read_text(encoding="utf-8")
    json_text = json.dumps(posts, ensure_ascii=False, separators=(",", ":"))
    neu, anzahl = re.subn(r"^(\s*const RAW = ).*;$", lambda m: m.group(1) + json_text + ";",
                          html, count=1, flags=re.M)
    if anzahl != 1:
        sys.exit("Zeile 'const RAW = ...;' nicht in der Seite gefunden")
    Path(seite).write_text(neu, encoding="utf-8")
    print(f"{len(posts)} Posts in {seite} geschrieben")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
