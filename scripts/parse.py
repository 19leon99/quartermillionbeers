import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone

# Erkennt deutsche WhatsApp-Exporte von Android und iPhone:
#   30.10.26, 19:29 - Name: Nachricht
#   [30.10.26, 19:29:05] Name: Nachricht
ZEILE = re.compile(
    r"^\[?(\d{1,2}\.\d{1,2}\.\d{2,4}),? (\d{1,2}:\d{2})(?::\d{2})?\]?(?: -)? ([^:]+): (.*)$"
)

# Was als Zähler-Nachricht gilt: hier "Nachricht besteht nur aus einer Zahl".
# Bei anderem Format diese Zeile anpassen.
ZAHL = re.compile(r"^\s*(\d{1,6})\s*$")

ZIEL = 250_000


def lies_datum(text):
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def main(eingabe, ausgabe):
    stand = None
    personen = Counter()
    verlauf = {}  # Datum -> letzter Stand des Tages

    with open(eingabe, encoding="utf-8") as f:
        for zeile in f:
            # unsichtbare Steuerzeichen aus dem Export entfernen
            zeile = zeile.replace("\u200e", "").replace("\u202f", " ").strip()
            treffer = ZEILE.match(zeile)
            if not treffer:
                continue
            datum_text, _, name, nachricht = treffer.groups()
            zahl = ZAHL.match(nachricht)
            datum = lies_datum(datum_text)
            if not zahl or not datum:
                continue

            n = int(zahl.group(1))
            # Plausibilitätscheck gegen Tippfehler: Stand muss leicht steigen
            if stand is not None and not (0 < n - stand <= 50):
                continue

            stand = n
            personen[name.strip()] += 1
            verlauf[datum.isoformat()] = stand

    daten = {
        "aktualisiert": datetime.now(timezone.utc).isoformat(),
        "stand": stand or 0,
        "ziel": ZIEL,
        "personen": [{"name": k, "biere": v} for k, v in personen.most_common()],
        "verlauf": [{"datum": d, "stand": s} for d, s in sorted(verlauf.items())],
    }

    with open(ausgabe, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    print(f"Stand: {daten['stand']}, Personen: {len(personen)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
