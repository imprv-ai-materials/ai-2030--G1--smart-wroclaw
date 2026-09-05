"""Generate the event-categorisation dataset for the DeepEval loop + Label Studio.

Run:  python eval/category_agent/generate_dataset.py   (from the smart_wroclaw/ root)

It emits, into eval/category_agent/data/:
  - category_dataset.jsonl   — every example, with a deterministic `split` tag
  - dev.jsonl / test.jsonl   — the stratified split (touch `test` rarely!)
  - label_studio_import.json — Label Studio tasks, PRE-ANNOTATED with the seed
                               labels as editable `predictions` (review, don't
                               label from scratch)
  - label_studio_config.xml  — the labelling interface for the LS project

The corpus below is a hand-authored seed: realistic Polish citizen reports across
all seven `ReportCategory` buckets, including deliberately hard / multi-topic /
no-keyword cases so the offline keyword baseline has real headroom to improve on.
It is a STARTING POINT — the whole point is that you enhance it in Label Studio,
export, and re-run. Split is deterministic (no RNG) so re-generating is stable.
"""

from __future__ import annotations

import json
from pathlib import Path

# --- the seven allowed labels (kept in sync with city_events_bc.ReportCategory) ---
CATEGORIES = ["WATER", "ROADS", "WASTE", "GREENERY", "LIGHTING", "PUBLIC_TRANSPORT", "OTHER"]

# Each row: (text, primary, secondary[list], difficulty, note)
# difficulty: easy | medium | hard  — hard = no obvious keyword or a misleading one.
CORPUS: list[tuple[str, str, list[str], str, str]] = [
    # ---------------- WATER ----------------
    ("Z hydrantu przy ul. Legnickiej tryska woda i zalewa cały chodnik.", "WATER", [], "easy", ""),
    ("Od trzech dni z pękniętej rury w piwnicy bloku przy Gajowej leci woda.", "WATER", [], "easy", ""),
    ("Studzienka kanalizacyjna na Powstańców Śląskich się przelewa i cuchnie.", "WATER", [], "medium", ""),
    (
        "Po każdej ulewie na skrzyżowaniu Grabiszyńskiej woda nie spływa i stoi wielka kałuża.",
        "WATER",
        [],
        "medium",
        "drenaż, nie sama droga",
    ),
    ("Brak wody w kranie w całej kamienicy na Nadodrzu od rana.", "WATER", [], "medium", ""),
    ("Wyciek z wodociągu pod jezdnią, asfalt zaczyna się zapadać.", "WATER", ["ROADS"], "hard", "woda niszczy drogę"),
    ("Zalany przystanek, woda z ulewy stoi do kostek i nie da się wsiąść.", "WATER", ["PUBLIC_TRANSPORT"], "hard", ""),
    ("Fontanna na rynku nie działa, woda jest brudna i zielona.", "WATER", [], "hard", "infrastruktura wodna"),
    ("Przeciek w suficie przejścia podziemnego, kapie wprost na przechodniów.", "WATER", [], "medium", ""),
    ("Uszkodzony, nieszczelny hydrant uliczny sączy wodę na Ołbinie.", "WATER", [], "easy", ""),
    ("Ścieki wypływają na powierzchnię trawnika w parku Grabiszyńskim.", "WATER", ["GREENERY"], "medium", ""),
    ("Zapadnięta studzienka ściekowa na chodniku, wydobywa się smród.", "WATER", [], "medium", ""),
    # ---------------- ROADS ----------------
    ("Głęboka dziura w jezdni na ul. Krakowskiej, można urwać koło.", "ROADS", [], "easy", ""),
    ("Zapadnięty chodnik przy ul. Kościuszki, wystają połamane płyty.", "ROADS", [], "easy", ""),
    ("Brakuje znaku STOP na skrzyżowaniu Borowska/Dyrekcyjna.", "ROADS", [], "medium", ""),
    (
        "Sygnalizacja świetlna na Placu Grunwaldzkim nie działa, miga na żółto.",
        "ROADS",
        [],
        "hard",
        "sygnalizacja = drogi, nie oświetlenie",
    ),
    ("Ubytek w nawierzchni ścieżki rowerowej wzdłuż Odry.", "ROADS", [], "medium", ""),
    ("Popękany, nierówny asfalt na Traugutta, auta podskakują.", "ROADS", [], "easy", ""),
    ("Uszkodzony krawężnik przy przejściu dla pieszych, ktoś się potknął.", "ROADS", [], "medium", ""),
    ("Rozbity próg zwalniający na osiedlu, kawałki leżą na drodze.", "ROADS", [], "medium", ""),
    ("Ogromna koleina na buspasie, przy deszczu robi się z niej rzeka.", "ROADS", ["WATER"], "hard", ""),
    ("Całkowicie starte pasy na przejściu dla pieszych, w ogóle ich nie widać.", "ROADS", [], "medium", ""),
    ("Wystająca, obluzowana pokrywa włazu na środku chodnika.", "ROADS", [], "medium", ""),
    ("Oznakowanie objazdu jest mylące, kierowcy jadą pod prąd.", "ROADS", [], "hard", "brak słowa-klucza"),
    # ---------------- WASTE ----------------
    ("Kosze na śmieci przy placu zabaw są przepełnione od tygodnia.", "WASTE", [], "easy", ""),
    ("Ktoś wyrzucił stare meble i gruz do lasku na Sołtysowicach.", "WASTE", [], "easy", ""),
    ("Kontener na odpady zmieszane nie był opróżniony w tym tygodniu.", "WASTE", [], "easy", ""),
    ("Dzikie wysypisko śmieci urządzono pod wiaduktem kolejowym.", "WASTE", [], "medium", ""),
    ("Worki ze śmieciami rozerwane, wiatr roznosi je po całym podwórku.", "WASTE", [], "medium", ""),
    ("Przepełniony pojemnik na szkło, butelki stoją porozstawiane obok.", "WASTE", [], "easy", ""),
    ("Ktoś porzucił lodówkę i telewizor przy altanie śmietnikowej.", "WASTE", [], "medium", ""),
    ("Zaśmiecony brzeg fosy, pełno plastikowych butelek dryfuje w wodzie.", "WASTE", ["WATER"], "hard", ""),
    ("Gruz po remoncie zalega na chodniku od miesiąca i nikt go nie zabiera.", "WASTE", ["ROADS"], "medium", ""),
    ("Pełno psich odchodów na trawniku, bo zniknął kosz i dystrybutor worków.", "WASTE", ["GREENERY"], "hard", ""),
    ("Sterta liści i śmieci zapchała rynsztok przy szkole.", "WASTE", ["GREENERY"], "medium", ""),
    ("Przepełniony kosz uliczny, śmieci walają się wokół ławek.", "WASTE", [], "easy", ""),
    # ---------------- GREENERY ----------------
    ("Złamana gałąź wisi nad ścieżką w Parku Południowym, grozi upadkiem.", "GREENERY", [], "easy", ""),
    ("Trawnik przy Powstańców nie był koszony całe lato, trawa po pas.", "GREENERY", [], "easy", ""),
    ("Uschnięte drzewo przy chodniku niebezpiecznie się pochyla.", "GREENERY", [], "medium", ""),
    ("Krzewy przy przejściu dla pieszych całkiem zasłaniają widoczność.", "GREENERY", ["ROADS"], "hard", ""),
    ("Wichura powaliła drzewo, leży w poprzek alejki parkowej.", "GREENERY", [], "easy", ""),
    ("Przerośnięty żywopłot wchodzi na ścieżkę rowerową i smaga rowerzystów.", "GREENERY", ["ROADS"], "medium", ""),
    (
        "Kasztanowce w alei są chore, zaatakowane przez szrotówka.",
        "GREENERY",
        [],
        "hard",
        "brak oczywistego słowa-klucza",
    ),
    ("Zaniedbany klomb na skwerze, same chwasty zamiast kwiatów.", "GREENERY", [], "medium", ""),
    ("Korzenie starego drzewa powypychały płyty chodnikowe do góry.", "GREENERY", ["ROADS"], "hard", ""),
    ("Gałęzie drzewa ocierają o trakcję tramwajową i iskrzą.", "GREENERY", ["PUBLIC_TRANSPORT"], "hard", ""),
    ("Wyłamany konar zablokował wjazd na parking osiedlowy.", "GREENERY", [], "medium", ""),
    ("Nowe nasadzenia na skwerze zostały połamane przez wandali.", "GREENERY", [], "medium", ""),
    # ---------------- LIGHTING ----------------
    ("Nie świeci latarnia przy przejściu dla pieszych, wieczorem jest ciemno.", "LIGHTING", [], "easy", ""),
    ("Cała ulica Sienkiewicza tonie w ciemności, zgasło oświetlenie.", "LIGHTING", [], "easy", ""),
    ("Lampa uliczna przed blokiem mruga i migocze przez całą noc.", "LIGHTING", [], "medium", ""),
    ("Przepalona żarówka w latarni na skwerze, punkt świetlny martwy.", "LIGHTING", [], "easy", ""),
    (
        "Uszkodzony słup oświetleniowy, zwisają z niego gołe kable.",
        "LIGHTING",
        [],
        "hard",
        "zagrożenie, ale to oświetlenie",
    ),
    ("W parku nie działa oświetlenie, mieszkańcy boją się chodzić po zmroku.", "LIGHTING", ["GREENERY"], "medium", ""),
    ("Zgasło oświetlenie na przystanku, po ciemku nie widać rozkładu.", "LIGHTING", ["PUBLIC_TRANSPORT"], "hard", ""),
    ("Latarnia świeci pełnym blaskiem w środku dnia, marnuje prąd.", "LIGHTING", [], "medium", ""),
    ("Na parkingu podziemnym zgasła połowa świetlówek, zrobiło się mroczno.", "LIGHTING", [], "medium", ""),
    ("Słup latarni przechylił się po kolizji i wisi nad jezdnią.", "LIGHTING", ["ROADS"], "hard", ""),
    ("Oświetlenie boiska osiedlowego nie działa już od miesiąca.", "LIGHTING", [], "easy", ""),
    # ---------------- PUBLIC_TRANSPORT ----------------
    ("Rozbita wiata przystankowa MPK na przystanku Rynek.", "PUBLIC_TRANSPORT", [], "easy", ""),
    ("Tramwaj linii 33 od tygodnia notorycznie spóźnia się w porannym szczycie.", "PUBLIC_TRANSPORT", [], "medium", ""),
    ("Zepsuty biletomat na przystanku Dworzec Główny, nie da się kupić biletu.", "PUBLIC_TRANSPORT", [], "easy", ""),
    ("Na słupku przystankowym brak aktualnego rozkładu jazdy.", "PUBLIC_TRANSPORT", [], "medium", ""),
    ("Autobus 128 w ogóle nie przyjechał, czekałem 40 minut na mrozie.", "PUBLIC_TRANSPORT", [], "medium", ""),
    ("W wiacie przystankowej wybite szyby i powyrywane siedzenia.", "PUBLIC_TRANSPORT", [], "medium", ""),
    ("Automat biletowy nie przyjmuje kart, działa tylko na gotówkę.", "PUBLIC_TRANSPORT", [], "medium", ""),
    ("Zniknął słupek przystankowy z numerami linii, nie wiadomo gdzie stanąć.", "PUBLIC_TRANSPORT", [], "hard", ""),
    (
        "Winda na przystanek kolejowy nie działa, nie wjadę wózkiem na peron.",
        "PUBLIC_TRANSPORT",
        [],
        "hard",
        "dostępność",
    ),
    ("Zaparkowane auto blokuje przejazd tramwaju, stoi cała linia.", "PUBLIC_TRANSPORT", [], "hard", ""),
    ("Oblodzony, nieodśnieżony peron przystanku tramwajowego, ślisko.", "PUBLIC_TRANSPORT", [], "hard", ""),
    # ---------------- OTHER ----------------
    ("Głośna impreza w sąsiednim mieszkaniu codziennie do trzeciej w nocy.", "OTHER", [], "easy", ""),
    ("Stado bezpańskich psów biega po osiedlu i straszy dzieci.", "OTHER", [], "medium", ""),
    ("Ktoś handluje bez zezwolenia na deptaku, zastawił całe przejście.", "OTHER", [], "hard", ""),
    ("Dziki przekopały cały teren przy blokach na Maślicach.", "OTHER", [], "hard", "zwierzęta, nie zieleń"),
    (
        "Samochód notorycznie parkuje na trawniku przy wejściu do klatki.",
        "OTHER",
        ["GREENERY"],
        "hard",
        "parkowanie + zieleń",
    ),
    ("Agresywny mężczyzna zaczepia i wyzywa przechodniów pod sklepem.", "OTHER", [], "medium", ""),
    ("Wandale porysowali i zniszczyli ławki na skwerze.", "OTHER", ["GREENERY"], "hard", ""),
    ("Publiczny szalet miejski na rynku jest nieczynny od dawna.", "OTHER", [], "medium", ""),
    ("Gniazdo szerszeni tuż przy placu zabaw, dzieci się boją.", "OTHER", ["GREENERY"], "hard", ""),
    (
        "Nie działa tablica miejskiego systemu rowerowego, nie wypożyczę roweru.",
        "OTHER",
        ["PUBLIC_TRANSPORT"],
        "hard",
        "",
    ),
]

DATA_DIR = Path(__file__).resolve().parent / "data"

_PREFIX = {
    "WATER": "wat",
    "ROADS": "roa",
    "WASTE": "was",
    "GREENERY": "gre",
    "LIGHTING": "lig",
    "PUBLIC_TRANSPORT": "pub",
    "OTHER": "oth",
}


def _build_rows() -> list[dict]:
    rows: list[dict] = []
    per_cat_counter: dict[str, int] = {}
    for text, primary, secondary, difficulty, note in CORPUS:
        assert primary in CATEGORIES, f"unknown primary {primary!r}"
        for s in secondary:
            assert s in CATEGORIES, f"unknown secondary {s!r}"
            assert s != primary, f"secondary repeats primary in {text!r}"
        n = per_cat_counter.get(primary, 0)
        per_cat_counter[primary] = n + 1
        # Deterministic stratified split: within each category, every 3rd → test.
        split = "test" if n % 3 == 2 else "dev"
        rows.append(
            {
                "id": f"{_PREFIX[primary]}-{n + 1:03d}",
                "text": text,
                "primary_category": primary,
                "secondary_categories": secondary,
                "difficulty": difficulty,
                "note": note,
                "split": split,
            }
        )
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _label_studio_tasks(rows: list[dict]) -> list[dict]:
    """LS import: each task carries the seed labels as an editable `prediction`
    so annotators review/correct instead of labelling from scratch."""
    tasks = []
    for r in rows:
        result = [
            {
                "from_name": "primary",
                "to_name": "text",
                "type": "choices",
                "value": {"choices": [r["primary_category"]]},
            }
        ]
        if r["secondary_categories"]:
            result.append(
                {
                    "from_name": "secondary",
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": r["secondary_categories"]},
                }
            )
        tasks.append(
            {
                "data": {"text": r["text"]},
                "predictions": [{"model_version": "seed-v1", "result": result}],
                "meta": {
                    "id": r["id"],
                    "split": r["split"],
                    "difficulty": r["difficulty"],
                    "note": r["note"],
                },
            }
        )
    return tasks


LABEL_CONFIG = """\
<View>
  <Header value="Zgłoszenie mieszkańca (kategoryzacja zdarzenia)"/>
  <Text name="text" value="$text"/>

  <View style="margin-top:1em">
    <Choices name="primary" toName="text" choice="single" required="true" showInline="false">
      <Header value="Kategoria główna (dokładnie jedna)"/>
      <Choice value="WATER"/>
      <Choice value="ROADS"/>
      <Choice value="WASTE"/>
      <Choice value="GREENERY"/>
      <Choice value="LIGHTING"/>
      <Choice value="PUBLIC_TRANSPORT"/>
      <Choice value="OTHER"/>
    </Choices>
  </View>

  <View style="margin-top:1em">
    <Choices name="secondary" toName="text" choice="multiple" required="false" showInline="true">
      <Header value="Kategorie dodatkowe (opcjonalne, gdy zgłoszenie dotyczy kilku obszarów)"/>
      <Choice value="WATER"/>
      <Choice value="ROADS"/>
      <Choice value="WASTE"/>
      <Choice value="GREENERY"/>
      <Choice value="LIGHTING"/>
      <Choice value="PUBLIC_TRANSPORT"/>
      <Choice value="OTHER"/>
    </Choices>
  </View>

  <TextArea name="notes" toName="text" rows="2" maxSubmissions="1"
            placeholder="Uwagi / uzasadnienie dla trudnych przypadków (opcjonalnie)"/>
</View>
"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = _build_rows()
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]

    _write_jsonl(DATA_DIR / "category_dataset.jsonl", rows)
    _write_jsonl(DATA_DIR / "dev.jsonl", dev)
    _write_jsonl(DATA_DIR / "test.jsonl", test)
    (DATA_DIR / "label_studio_import.json").write_text(
        json.dumps(_label_studio_tasks(rows), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "label_studio_config.xml").write_text(LABEL_CONFIG, encoding="utf-8")

    # Console summary — counts per category and split, so the balance is visible.
    print(f"total={len(rows)}  dev={len(dev)}  test={len(test)}")
    print("per-category (dev/test):")
    for cat in CATEGORIES:
        d = sum(1 for r in dev if r["primary_category"] == cat)
        t = sum(1 for r in test if r["primary_category"] == cat)
        print(f"  {cat:<17} {d:>2}/{t:<2}")
    multi = sum(1 for r in rows if r["secondary_categories"])
    print(f"multi-category examples: {multi}")
    print(f"written → {DATA_DIR}")


if __name__ == "__main__":
    main()
