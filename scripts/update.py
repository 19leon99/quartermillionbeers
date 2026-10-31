"""Hängt neue Bier-Posts aus einem WhatsApp-Export an daten/posts.json an.

Aufruf:  python scripts/update.py chat/export.txt daten/posts.json

Die bisherigen Einträge in posts.json bleiben unverändert (sie sind von Hand
geprüft). Nur Posts, die NACH dem letzten Eintrag liegen, werden automatisch
ausgewertet und angehängt. Unsichere Fälle landen zusätzlich in
daten/pruefen.md, damit man sie bei Bedarf in daten/korrekturen.json
nachbessern kann.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# WhatsApp-Name -> Name auf der Website
NAMEN = {
    "Bastian": "Basti",
    "Tim Wesenbär 🐻": "Wese",
    "Tim Schneider": "Tim",
    "Philipp Schneider": "Philipp",
    "T-D": "TD",
    "Nils": "Rentschi",
    "Zero MoRizz": "Moritz",
    "felix H": "Felix",
    "Jan Raiss": "Jan",
    "Janis f": "Janis",
    "Manu": "Manuel",
    "Sebastian Ruff": "Ruff",
    "Eric Kistner": "Kistner",
    "Leo Neumann": "Leo",
    "Jonas ⚜️": "Jonas",
    "Lasse B": "Lasse",
    "Stefan M": "Stefan",
}

def name(absender):
    return NAMEN.get(absender, absender.split()[0])


TAGESWECHSEL = 6  # Posts vor 6 Uhr zählen zum vorherigen Abend ("Partytag")
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

ZEILE = re.compile(r"^\[(\d{1,2}\.\d{1,2}\.\d{2,4}), (\d{1,2}:\d{2})(?::\d{2})?\] ([^:]+): ?(.*)$")
MEDIEN = re.compile(r"(Bild|Video) weggelassen")
UNSICHTBAR = dict.fromkeys(map(ord, "‎‏⁨⁩﻿"), None)


# ---------------------------------------------------------------- Export lesen

def lies_export(pfad):
    """Liefert Nachrichten als Dicts: zeit, absender, text, medien."""
    nachrichten = []
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.translate(UNSICHTBAR).replace(" ", " ").rstrip("\n")
            m = ZEILE.match(zeile)
            if m:
                datum, uhrzeit, absender, text = m.groups()
                fmt = "%d.%m.%y %H:%M" if len(datum.split(".")[2]) == 2 else "%d.%m.%Y %H:%M"
                nachrichten.append({
                    "zeit": datetime.strptime(f"{datum} {uhrzeit}", fmt),
                    "absender": absender.strip(),
                    "text": text,
                })
            elif nachrichten:  # Folgezeile einer mehrzeiligen Nachricht
                nachrichten[-1]["text"] += "\n" + zeile
    # WhatsApp sortiert nicht immer streng nach Zeit
    nachrichten.sort(key=lambda n: n["zeit"])
    for n in nachrichten:
        n["medien"] = bool(MEDIEN.search(n["text"]))
        text = MEDIEN.sub("", n["text"])
        text = text.replace("<Diese Nachricht wurde bearbeitet.>", "")
        text = re.sub(r"@\S+", "", text)  # Erwähnungen wie @Nils
        n["text"] = text.strip()
    return nachrichten


# ------------------------------------------------------------ Zahlen erkennen

def zahlen_aus(text):
    """Liest die Biernummern aus einer Bildunterschrift.

    Gibt (liste_der_nummern, plus_anzahl) zurück.
    "1006-1009" -> [1006..1009], "640-42" -> [640, 641, 642],
    "1463,4" -> [1463, 1464], "+3" -> ([], 3).
    """
    if not text:
        return [], 0
    erste_zeile = text.split("\n")[0]
    plus = re.search(r"\+\s?(\d)\b", erste_zeile)
    if plus and not re.search(r"\d{2,}", erste_zeile):  # "+3", "Haben nochmal +3"
        return [], int(plus.group(1))

    nummern = []
    for teil in re.finditer(r"(\d+)(?:\s*[-–]\s*(\d+))?", erste_zeile):
        a, b = teil.group(1), teil.group(2)
        if nummern and len(a) < len(str(nummern[0])):  # Kurzform "1463,4"
            a = str(nummern[-1])[: len(str(nummern[-1])) - len(a)] + a
        start = int(a)
        if b:
            if len(b) < len(a):  # Kurzform "640-42"
                b = a[: len(a) - len(b)] + b
            ende = int(b)
            if 0 < ende - start < 10:
                nummern.extend(range(start, ende + 1))
                continue
        nummern.append(start)
    return nummern, 0


# -------------------------------------------------- Nachrichten zu Bier-Posts

def zu_posts(nachrichten):
    """Fasst Bilder und nachgeschobene Nummern zu Bier-Posts zusammen."""
    posts = []
    letzter_von = {}
    text_vorab = {}  # Nummer als Text kurz VOR dem Bild geschickt
    for n in nachrichten:
        if n["medien"]:
            nummern, plus = zahlen_aus(n["text"])
            vorab = text_vorab.pop(n["absender"], None)
            if not nummern and not plus and vorab and n["zeit"] - vorab[0] <= timedelta(minutes=2):
                nummern, plus = vorab[1]
            # doppelt geschicktes Bild (gleiche Person, gleiche Nummer, < 2 Min.)
            vorher = letzter_von.get(n["absender"])
            if (vorher and nummern and vorher["nummern"] == nummern
                    and n["zeit"] - vorher["zeit"] <= timedelta(minutes=2)):
                continue
            post = {"zeit": n["zeit"], "absender": n["absender"], "text": n["text"],
                    "nummern": nummern, "plus": plus}
            posts.append(post)
            letzter_von[n["absender"]] = post
            continue

        # reine Textnachricht: nur interessant, wenn sie eine Nummer nachreicht
        roh = n["text"].strip()
        if not re.fullmatch(r"\*?\s?\d[\d\s,+&/\-–]*\*?|\(\d+\)", roh):
            continue
        nummern, plus = zahlen_aus(roh.strip("*()"))
        text_vorab[n["absender"]] = (n["zeit"], (nummern, plus))
        vorher = letzter_von.get(n["absender"])
        if not vorher or n["zeit"] - vorher["zeit"] > timedelta(minutes=5):
            continue
        if not vorher["nummern"] and not vorher["plus"]:
            vorher["nummern"], vorher["plus"] = nummern, plus  # Nummer nachgereicht
        elif "*" in roh:
            vorher["nummern"] = nummern  # Korrektur wie "1640*"
    return posts


# ------------------------------------------------------- Zählerstand prüfen

def bewerte(posts, stand, versatz):
    """Ordnet jedem Post den korrigierten Zählerstand zu.

    stand   = letzter korrigierter Zählerstand
    versatz = Differenz zwischen korrigiertem und gepostetem Zähler
              (die Gruppe hat sich zwischendurch um 100 verzählt)
    """
    zeilen, unsicher = [], []
    nummerierte = [i for i, p in enumerate(posts) if p["nummern"]]

    def abstand(nummer, k, basis, v):
        return abs(nummer + v - basis - k)

    def passend(nummer, k, basis, erwartet_versatz):
        """Bester Versatz (Vielfaches von 100), mit dem die Nummer nah am Stand liegt."""
        kandidaten = [erwartet_versatz + j * 100 for j in range(-3, 4)]
        gut = [v for v in kandidaten if abstand(nummer, k, basis, v) <= 40]
        return min(gut, key=lambda v: (abstand(nummer, k, basis, v), v != erwartet_versatz)) if gut else None

    for i, p in enumerate(posts):
        person = name(p["absender"])
        bemerkung = ""
        if p["nummern"]:
            k = len(p["nummern"])
            # letzte Nummer der Liste, die zum Stand passt ("486,487,4888" -> 487)
            gepostet, v = p["nummern"][-1], None
            for n in reversed(p["nummern"]):
                v = passend(n, k, stand, versatz)
                if v is not None:
                    gepostet = n
                    break
            if v is None:
                if (re.fullmatch(r"[\d\s,+&/\-–*]+", p["text"] or "x")
                        and len(str(gepostet)) <= len(str(max(stand, 1)))):
                    # reine Zahl, aber verzählt: Bier zählen, Zähler nicht verschieben
                    grund = f"Nummer passt nicht (gepostet {gepostet}), als {k} Bier gezählt"
                    unsicher.append((p, grund))
                    zeilen.append(zeile(p, person, str(gepostet), 0, stand, grund, k))
                else:  # z. B. "Kloschüssel Nr.1" oder "50 oder 100 Bier?"
                    unsicher.append((p, f"Nummer {gepostet} passt nicht zum Stand {stand}, nicht gezählt"))
                continue
            else:
                if v != versatz:
                    # Passt auch der nächste nummerierte Post besser zum neuen Versatz,
                    # hat sich die Gruppe verzählt -> übernehmen. Sonst Tippfehler.
                    weiter = [j for j in nummerierte if j > i][:1]
                    folgt = False
                    if weiter:
                        q = posts[weiter[0]]
                        qn, qk = q["nummern"][-1], len(q["nummern"])
                        folgt = abstand(qn, qk, gepostet + v, v) < abstand(qn, qk, gepostet + v, versatz)
                    if folgt:
                        bemerkung = (f"Zähler verrutscht (gepostet {gepostet} statt {gepostet + v}); "
                                     f"ab hier {v:+d} korrigiert")
                        versatz = v
                    else:
                        bemerkung = f"Tippfehler, gepostet als {gepostet}"
                neu = gepostet + v
                if neu < stand and not bemerkung:
                    # Folgt die Gruppe der niedrigeren Zahl, wurde der Zähler
                    # bewusst zurückgesetzt; sonst war die Nummer schon vergeben.
                    weiter = [j for j in nummerierte if j > i][:1]
                    if weiter:
                        q = posts[weiter[0]]
                        qn, qk = q["nummern"][-1], len(q["nummern"])
                        if abstand(qn, qk, neu, versatz) < abstand(qn, qk, stand + k, versatz):
                            bemerkung = f"Gruppe setzt den Zähler auf {neu} zurück"
                    if not bemerkung:
                        bemerkung = f"Nummer schon vergeben (gepostet {gepostet})"
                if bemerkung.startswith(("Tippfehler", "Nummer schon")):
                    neu = stand + k
                if neu < stand - 3 or neu > stand + k + 8:
                    unsicher.append((p, f"Zählersprung von {stand} auf {neu}"))
            im_bild = neu - stand
            gezaehlt = k if k > 1 else (im_bild if 1 <= im_bild <= 6 else 1)
            nummer = str(gepostet)
        elif p["plus"]:
            neu, im_bild, gezaehlt, nummer = stand, 0, p["plus"], ""
            bemerkung = f"ohne Nummer gepostet (+{p['plus']})"
        else:
            unsicher.append((p, "Bild ohne Nummer, nicht gezählt"))
            continue

        stand = neu
        zeilen.append(zeile(p, person, nummer, im_bild, stand, bemerkung, gezaehlt))
    return zeilen, unsicher


def zeile(p, person, nummer, im_bild, stand, bemerkung, gezaehlt):
    """Eine Datenzeile im Format der Website."""
    partytag = (p["zeit"] - timedelta(hours=TAGESWECHSEL)).date()
    return {
        "zeit": p["zeit"].strftime("%Y-%m-%dT%H:%M"),
        "partytag": partytag.isoformat(),
        "tag_label": f"{WOCHENTAGE[partytag.weekday()]} {partytag:%d.%m.}",
        "woche": (partytag - timedelta(days=partytag.weekday())).isoformat(),
        "stunde": str(p["zeit"].hour),
        "person": person,
        "nummer": nummer,
        "biere_im_bild": str(im_bild),
        "nummer_korr": str(stand),
        "bemerkung": bemerkung,
        "biere_gezaehlt": str(gezaehlt),
    }


# ---------------------------------------------------------------- Hauptteil

def korrekturen_anwenden(posts, pfad):
    """daten/korrekturen.json: Einträge überschreiben, entfernen oder ergänzen.

    [{"zeit": "2026-11-01T21:15", "person": "Basti", "biere_gezaehlt": "2"},
     {"zeit": "2026-11-01T21:20", "person": "Jan", "entfernen": true},
     {"neu": {...vollständige Zeile...}}]
    """
    if not Path(pfad).exists():
        return posts
    for k in json.loads(Path(pfad).read_text(encoding="utf-8")):
        if "neu" in k:
            if k["neu"] not in posts:
                posts.append(k["neu"])
            continue
        treffer = [p for p in posts if p["zeit"] == k["zeit"] and p["person"] == k["person"]]
        for p in treffer:
            if k.get("entfernen"):
                posts.remove(p)
            else:
                p.update({f: v for f, v in k.items() if f not in ("zeit", "person")})
    posts.sort(key=lambda p: p["zeit"])
    return posts


def main(export, ziel):
    ziel = Path(ziel)
    bisher = json.loads(ziel.read_text(encoding="utf-8")) if ziel.exists() else []

    posts = zu_posts(lies_export(export))
    if bisher:
        letzte = bisher[-1]
        stand = int(letzte["nummer_korr"])
        mit_nummer = [b for b in bisher if b["nummer"]]
        versatz = int(mit_nummer[-1]["nummer_korr"]) - int(mit_nummer[-1]["nummer"]) if mit_nummer else 0
        schon_da = {(b["zeit"], b["person"]) for b in bisher if b["zeit"] == letzte["zeit"]}
        posts = [p for p in posts
                 if p["zeit"].strftime("%Y-%m-%dT%H:%M") > letzte["zeit"]
                 or (p["zeit"].strftime("%Y-%m-%dT%H:%M") == letzte["zeit"]
                     and (letzte["zeit"], name(p["absender"])) not in schon_da)]
    else:
        stand, versatz = 0, 0

    neu, unsicher = bewerte(posts, stand, versatz)
    alle = korrekturen_anwenden(bisher + neu, ziel.parent / "korrekturen.json")
    ziel.write_text(json.dumps(alle, ensure_ascii=False, indent=0), encoding="utf-8")

    pruefen = ziel.parent / "pruefen.md"
    with open(pruefen, "w", encoding="utf-8") as f:
        f.write("# Zu prüfen (letztes Update)\n\n")
        for p, grund in unsicher:
            person = name(p["absender"])
            f.write(f"- {p['zeit']:%Y-%m-%dT%H:%M} · {person} · „{p['text'][:60]}“ → {grund}\n")
        if not unsicher:
            f.write("Nichts Auffälliges.\n")

    print(f"{len(neu)} neue Posts, {sum(int(z['biere_gezaehlt']) for z in neu)} Bier, "
          f"Zählerstand jetzt {alle[-1]['nummer_korr'] if alle else 0}, {len(unsicher)} zu prüfen")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
