"""Intent detection and constraint extraction (FR-C1/C2) in EN/FR/DE/IT.

Two layers:
1. `detect()` — deterministic keyword/regex classifier. Fast, testable, used directly in plugin mode helpers
   and as the fallback/validator in standalone mode.
2. `LLM_SCHEMA` / `LLM_PROMPT` — what the standalone agent asks the model for; the result is validated into
   the same `Detection` shape. An attachment always implies `audit`. Emergency phrases short-circuit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from bergbot.core.domain import Constraint, Intent, QuestionKind
from bergbot.i18n import Lang

# ----- language detection -----
_LANG_HINTS: dict[Lang, list[str]] = {
    "de": [
        "wanderung",
        "morgen",
        "kanton",
        "höhenmeter",
        "ich",
        "und",
        "mit",
        "hütte",
        "ist",
        "der",
        "die",
        "das",
        "nach",
        "gibt",
        "kann",
        "eine",
        "einen",
        "bitte",
        "übermorgen",
        "hoi",
        "grüezi",
        "danke",
        "welche",
        "wie",
        "was",
        "offen",
        "fährt",
        "gilt",
        "im",
        "gerade",
        "ein",
        "schick",
        "mir",
        "kürzer",
        "länger",
        "einfacher",
        "noch",
        "etwas",
        "bei",
        "ab",
        "zug",
        "dem",
        "am",
        "zum",
        "zur",
        "über",
        "unter",
        "max",
        "rauf",
        "zurück",
        "leichte",
        "leicht",
        "gefährlich",
        "kind",
        "hund",
    ],
    "fr": [
        "randonnée",
        "rando",
        "demain",
        "canton",
        "dénivelé",
        "je",
        "avec",
        "cabane",
        "est",
        "le",
        "la",
        "les",
        "une",
        "un",
        "vers",
        "près",
        "bonjour",
        "salut",
        "merci",
        "quel",
        "quelle",
        "comment",
        "ouvert",
        "fonctionne",
        "est-ce",
        "envoie",
        "moi",
        "plus",
        "court",
        "courte",
        "long",
        "au",
        "aux",
        "du",
        "des",
        "de",
        "et",
        "il",
        "y",
        "a-t-il",
        "en",
        "ce",
        "moment",
        "pour",
        "dangereux",
        "enfants",
        "chien",
        "facile",
        "moins",
        "retour",
        "train",
        "dimanche",
        "samedi",
        "quelque",
        "chose",
        "tombé",
        "blessé",
    ],
    "it": [
        "escursione",
        "domani",
        "cantone",
        "dislivello",
        "io",
        "con",
        "capanna",
        "è",
        "il",
        "una",
        "un",
        "vicino",
        "ciao",
        "grazie",
        "quale",
        "come",
        "cosa",
        "aperta",
        "aperto",
        "funziona",
        "gita",
        "sentiero",
        "c'è",
        "in",
        "questo",
        "momento",
        "inviami",
        "più",
        "corta",
        "corto",
        "divieto",
        "fuochi",
        "meno",
        "di",
        "da",
        "treno",
        "ritorno",
        "domenica",
        "sabato",
        "qualcosa",
        "pericoloso",
        "bambini",
        "cane",
        "facile",
        "salita",
        "caduto",
        "ferito",
        "lago",
        "all'arrivo",
        "della",
        "del",
    ],
    "en": [
        "hike",
        "tomorrow",
        "canton",
        "ascent",
        "with",
        "hut",
        "is",
        "the",
        "near",
        "hello",
        "hi",
        "thanks",
        "which",
        "how",
        "what",
        "open",
        "running",
        "trail",
        "please",
        "weekend",
        "me",
        "my",
        "send",
        "shorter",
        "longer",
        "easier",
        "another",
        "something",
        "from",
        "by",
        "train",
        "under",
        "less",
        "than",
        "up",
        "in",
        "of",
        "and",
        "for",
        "this",
        "route",
        "photos",
        "dangerous",
        "kids",
        "dog",
        "lunch",
        "easy",
        "back",
        "sunday",
        "saturday",
        "fell",
        "injured",
        "someone",
    ],
}
_LANG_STRONG: dict[Lang, list[str]] = {
    "de": [
        "wanderung",
        "wandern",
        "morgen",
        "höhenmeter",
        "hütte",
        "kanton",
        "fährt",
        "gesperrt",
        "übermorgen",
        "gibt es",
        "ich möchte",
        "ich will",
        "schick mir",
        "gilt im",
        "kürzer",
        "länger",
        "hüttenzmittag",
        "feuerverbot",
        "gestürzt",
        "verletzt",
    ],
    "fr": [
        "randonnée",
        "rando",
        "demain",
        "dénivelé",
        "cabane",
        "est-ce",
        "près de",
        "je veux",
        "j'aimerais",
        "autour de",
        "envoie-moi",
        "plus court",
        "plus courte",
        "y a-t-il",
        "interdiction",
        "fonctionne",
        "quelqu'un",
        "blessé",
        "quelque chose",
    ],
    "it": [
        "escursione",
        "domani",
        "dislivello",
        "capanna",
        "vicino a",
        "vorrei",
        "funziona",
        "gita",
        "inviami",
        "più corta",
        "più corto",
        "c'è",
        "divieto",
        "qualcuno",
        "ferito",
        "qualcosa",
        "pericoloso",
    ],
    "en": [
        "hike",
        "hiking",
        "tomorrow",
        "ascent",
        "hut lunch",
        "near",
        "i want",
        "i'd like",
        "running",
        "weekend",
        "send me",
        "shorter",
        "someone fell",
        "photos of",
        "what is",
        "is it",
        "is the",
        "can you",
    ],
}


def detect_language(text: str, default: Lang = "en") -> Lang:
    t = f" {text.lower()} "
    scores: dict[Lang, float] = {}
    lang: Lang
    for lang in ("en", "fr", "de", "it"):
        s = 0.0
        for w in _LANG_STRONG[lang]:
            if f" {w} " in t or t.strip().startswith(w) or f" {w}," in t or f" {w}?" in t:
                s += 3
        for w in _LANG_HINTS[lang]:
            s += len(re.findall(rf"(?<![\w'])({re.escape(w)})(?![\w'])", t))
        scores[lang] = s
    if any(ch in t for ch in "äöüß") and scores["de"] >= scores["fr"]:
        scores["de"] += 1
    if any(ch in t for ch in "éèêàçù") and scores["fr"] + scores["it"] > 0:
        scores["fr"] += 0.5
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else default


# ----- intent keywords -----
EMERGENCY = re.compile(
    r"\b(someone fell|injured|lost and|we are lost|i am lost|emergency|help me now|accident|unconscious|"
    r"jemand ist gestürzt|verletzt|notfall|wir haben uns verirrt|abgestürzt|"
    r"quelqu'un est tombé|blessé|urgence|nous sommes perdus|accident|"
    r"qualcuno è caduto|ferito|emergenza|ci siamo persi|incidente)\b",
    re.I,
)
HELP = re.compile(
    r"^\s*(help|aide|hilfe|aiuto|what can you do|que peux-tu faire|was kannst du|cosa sai fare|/help|/start|hi|hello|hey|salut|bonjour|hallo|hoi|grüezi|ciao|buongiorno)\s*[!?.]*\s*$",
    re.I,
)
CHECK = re.compile(
    r"\b(is the .*(running|open|operating|closed)|is there a fire ban|fire ban|lift (running|open)|(gondola|cableway|cable car|funicular|hut|pass|road) .*(open|running|closed)|"
    r"fährt (die|der|das)|ist (die|der|das) .*(offen|geöffnet|in betrieb|gesperrt|geschlossen)|feuerverbot|"
    r"fonctionne|est-ce que .*(ouvert|ouverte|ferm)|interdiction de (faire du )?feu|le (col|téléphérique|télécabine|refuge|cabane) .*(ouvert|ferm)|"
    r"funziona|è (aperta|aperto|chiusa|chiuso)|divieto di (accendere )?fuoch)",
    re.I,
)
EXPORT = re.compile(r"\b(gpx|kml|geojson|send me the file|export|exporter|exportieren|esporta)\b", re.I)
MEDIA = re.compile(
    r"\b(photos?|pictures|stories|fotos?|bilder|geschichten|images|récits|immagini|racconti|video)\b", re.I
)
AROUND = re.compile(
    r"\b(near|around|close to|from|starting (at|from)|in der nähe von|rund um|um .* herum|ab |bei |"
    r"près de|autour de|à côté de|depuis|au départ de|vicino a|attorno a|nei dintorni di|da )",
    re.I,
)
FIND_WORDS = re.compile(
    r"\b(hike|hiking|walk|trail|route|tour|suggest|find|generate|recommend|idea|wanderung|wandern|tour|vorschlag|"
    r"randonnée|rando|balade|itinéraire|propose|trouve|escursione|gita|sentiero|proposta|trova|percorso)\b",
    re.I,
)
SELECT = re.compile(
    r"^\s*(?:option\s*|nr\.?\s*|no\.?\s*|number\s*|numéro\s*|nummer\s*|numero\s*)?([1-3])\b[\s.)!]*$|^\s*(the first|the second|the third|la première|la deuxième|la troisième|die erste|die zweite|die dritte|la prima|la seconda|la terza|first one|second one|third one)\b",
    re.I,
)
ANOTHER = re.compile(
    r"\b(another|other suggestion|something else|next one|une autre|autre chose|une autre proposition|noch eine|etwas anderes|ein anderer vorschlag|un'altra|un altro|qualcos'altro)\b",
    re.I,
)
MODIFY = re.compile(
    r"\b(shorter|longer|easier|harder|less climb|flatter|instead|with a hut|without|from the other side|sunday|saturday|"
    r"kürzer|länger|einfacher|leichter|schwerer|weniger|stattdessen|mit hütte|ohne|von der anderen seite|sonntag|samstag|"
    r"plus court|plus courte|plus long|plus facile|moins|plutôt|avec une cabane|sans|de l'autre côté|dimanche|samedi|"
    r"più corta|più corto|più lunga|più facile|meno|invece|con capanna|senza|dall'altro lato|domenica|sabato)\b",
    re.I,
)
SAFETY_Q = re.compile(
    r"\b(dangerous|danger|risky|is it ok for|can i take (my )?(kids?|children|child)|with (a |my )?(kid|child|children)|8[- ]year|is the snow gone|"
    r"gefährlich|gefahr|kann ich (mein|die) kind|mit kindern|jährige|ist der schnee weg|"
    r"dangereux|dangereuse|danger|risqué|avec (des|mes|un) enfant|de 8 ans|la neige est|"
    r"pericoloso|pericolosa|pericolo|rischioso|con (i |un )?bambin|di 8 anni|la neve è)\b",
    re.I,
)
QUESTION = re.compile(
    r"\?\s*$|^\s*(what|which|how|why|when|where|is |are |does |can |quel|quelle|comment|pourquoi|est-ce|was |welche|wie |warum|wann|wo |ist |gibt|kann|cosa|quale|come |perché|quando|dove |è |c'è|posso)",
    re.I,
)

MONTHS = {
    "en": [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ],
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "de": [
        "januar",
        "februar",
        "märz",
        "april",
        "mai",
        "juni",
        "juli",
        "august",
        "september",
        "oktober",
        "november",
        "dezember",
    ],
    "it": [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ],
}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonntag": 6,
    "lunedì": 0,
    "martedì": 1,
    "mercoledì": 2,
    "giovedì": 3,
    "venerdì": 4,
    "sabato": 5,
    "domenica": 6,
}
CANTON_NAMES = {
    "ag": ["aargau", "argovie", "argovia"],
    "ai": ["appenzell innerrhoden"],
    "ar": ["appenzell ausserrhoden"],
    "be": ["bern", "berne", "berna"],
    "bl": ["basel-landschaft", "baselland"],
    "bs": ["basel-stadt", "basel"],
    "fr": ["fribourg", "freiburg", "friburgo"],
    "ge": ["geneva", "genève", "genf", "ginevra"],
    "gl": ["glarus", "glaris", "glarona"],
    "gr": ["graubünden", "grisons", "grigioni", "graubunden", "grischun"],
    "ju": ["jura"],
    "lu": ["lucerne", "luzern", "lucerna"],
    "ne": ["neuchâtel", "neuenburg", "neuchatel"],
    "nw": ["nidwalden", "nidwald"],
    "ow": ["obwalden", "obwald"],
    "sg": ["st. gallen", "st gallen", "saint-gall", "san gallo"],
    "sh": ["schaffhausen", "schaffhouse", "sciaffusa"],
    "so": ["solothurn", "soleure", "soletta"],
    "sz": ["schwyz", "schwytz", "svitto"],
    "tg": ["thurgau", "thurgovie", "turgovia"],
    "ti": ["ticino", "tessin"],
    "ur": ["uri"],
    "vd": ["vaud", "waadt"],
    "vs": ["valais", "wallis", "vallese"],
    "zg": ["zug", "zoug", "zugo"],
    "zh": ["zürich", "zurich", "zurigo", "zuerich"],
}
CANTON_PREFIX = re.compile(
    r"\b(canton|kanton|cantone|kt\.?)\s+(?:of |de |du |di |des |von )?([A-Za-zÀ-ÿ.\- ]{2,25})", re.I
)
GRADE = re.compile(r"\bT\s?([1-6])\b", re.I)
EASY = re.compile(
    r"\b(easy|facile|leicht|einfach|gemütlich|beginner|family|famille|familie|famiglia|kids|enfants|kinder|bambini|flat|plat|flach|pianeggiante|tranquilla)\b",
    re.I,
)
ASCENT = re.compile(
    r"(?:under|less than|max(?:imum)?|below|at most|unter|weniger als|höchstens|maximal|moins de|max|meno di|al massimo|sotto i?)\s*(\d{2,4})\s*(?:m\b|meters|metres|meter|mètres|metri|hm\b|höhenmeter|de dénivelé|dislivello|of ascent|up\b|climb)",
    re.I,
)
ASCENT2 = re.compile(
    r"(\d{2,4})\s*(?:m\b|meters|metres|meter|mètres|metri)\s*(?:of )?(?:ascent|up|climb|elevation|dénivelé|d\+|höhenmeter|aufstieg|dislivello|di salita|de montée|hoch|rauf)",
    re.I,
)
DISTANCE = re.compile(
    r"(?:under|less than|max(?:imum)?|at most|unter|weniger als|höchstens|maximal|moins de|meno di|al massimo)?\s*(\d{1,2}(?:[.,]\d)?)\s*(?:km|kilomet)",
    re.I,
)
DURATION = re.compile(
    r"(?:under|less than|max(?:imum)?|at most|about|around|unter|weniger als|höchstens|etwa|ca\.?|moins de|environ|meno di|circa)?\s*(\d{1,2}(?:[.,]\d)?)\s*(?:h\b|hours?|hrs|stunden|std|heures?|ore)\b(?!\s*(?:from|de|von|da|ab)\b)",
    re.I,
)
TRAVEL = re.compile(
    r"(?:under|less than|max|within|unter|weniger als|höchstens|moins de|meno di|entro|a meno di)\s*(\d{1,2}(?:[.,]\d)?)\s*(?:h\b|hours?|hrs|stunden|heures?|ore)\s*(?:from|by train from|de|von|da|ab)\s+([A-ZÀ-Ý][\wÀ-ÿ.\- ]{2,30}?)(?:\s+(?:by|en|mit|in|con)\b|[,.!?]|$)",
    re.I,
)
BY_TRANSPORT = re.compile(
    r"\b(by (train|bus|public transport|transit)|back by train|train back|with (the )?train|öv|öffentlich|mit dem zug|mit zug|zurück mit dem zug|en train|transports? publics?|en transports|in treno|con i mezzi|mezzi pubblici)\b",
    re.I,
)
HUT = re.compile(
    r"\b(hut|hütte\w*|cabane|refuge|capanna|rifugio|lunch|\w*zmittag|mittagessen|repas|pranzo|restaurant|beiz)\b",
    re.I,
)
DOG = re.compile(r"\b(dog|hund|chien|cane)\b", re.I)
BIVOUAC = re.compile(r"\b(bivouac|biwak|bivacc|camp|zelt|tente|tenda)", re.I)
WATER = re.compile(r"\b(water|wasser|eau|acqua)\b", re.I)
LOOP = re.compile(
    r"\b(loop|round trip|circular|rundweg|rundwanderung|rundtour|boucle|circuit|anello|circolare)\b", re.I
)
KIDS = re.compile(
    r"\b(kids?|children|child|family|kinder|familie|enfants?|famille|bambin[oi]|famiglia)\b", re.I
)
SENIORS = re.compile(r"\b(seniors?|grandparents|senioren|grosseltern|personnes âgées|anziani|nonni)\b", re.I)
NEAR_PLACE = re.compile(
    r"(?:near|around|close to|starting (?:at|from)|from|in der nähe von|rund um|bei|ab|près de|autour de|à côté de|depuis|au départ de|vicino a|attorno a|nei dintorni di|da)\s+([A-ZÀ-Ý][\wÀ-ÿ.'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ.'\-]+){0,2})",
)
FILE_ATTACH = re.compile(r"\b[\w\-. ]+\.(gpx|kml|geojson)\b", re.I)


@dataclass
class Detection:
    intent: Intent
    lang: Lang
    constraints: Constraint
    question: QuestionKind = QuestionKind.none
    selection: int | None = None
    confidence: float = 0.6
    reasons: list[str] = field(default_factory=list)


def detect(
    text: str, has_attachment: bool = False, today: date | None = None, lang_hint: str | None = None
) -> Detection:
    today = today or date.today()
    lang = detect_language(text, default=lang_hint or "en")  # type: ignore[arg-type]
    c = extract_constraints(text, lang, today)
    reasons: list[str] = []
    q = QuestionKind.safety if SAFETY_Q.search(text) else QuestionKind.none

    if EMERGENCY.search(text):
        return Detection(
            Intent.emergency, lang, c, QuestionKind.safety, confidence=0.95, reasons=["emergency phrase"]
        )
    if has_attachment or FILE_ATTACH.search(text):
        return Detection(Intent.audit, lang, c, q, confidence=0.95, reasons=["attachment"])
    m = SELECT.match(text.strip())
    if m:
        if m.group(1):
            n = int(m.group(1))
        else:
            word = m.group(2).lower()
            n = (
                1
                if any(k in word for k in ("first", "premi", "erste", "prima"))
                else 2
                if any(k in word for k in ("second", "deux", "zweite", "seconda"))
                else 3
            )
        return Detection(Intent.select, lang, c, q, selection=n, confidence=0.9, reasons=["selection"])
    if HELP.match(text.strip()) or len(text.strip()) < 3:
        return Detection(Intent.help, lang, c, q, confidence=0.9, reasons=["greeting/help"])
    if EXPORT.search(text) and not FIND_WORDS.search(text) and len(text.split()) <= 8:
        return Detection(Intent.export, lang, c, q, confidence=0.85, reasons=["export word"])
    if MEDIA.search(text) and len(text.split()) <= 8 and not _has_constraint(c):
        return Detection(Intent.media, lang, c, q, confidence=0.8, reasons=["media word"])
    if CHECK.search(text):
        return Detection(Intent.check, lang, c, q, confidence=0.85, reasons=["status question"])
    if ANOTHER.search(text) and len(text.split()) <= 8:
        return Detection(Intent.modify, lang, c, q, confidence=0.8, reasons=["another"])
    if MODIFY.search(text) and len(text.split()) <= 8 and not FIND_WORDS.search(text) and not c.place:
        return Detection(Intent.modify, lang, c, q, confidence=0.75, reasons=["modification"])
    if q is QuestionKind.safety and not FIND_WORDS.search(text):
        return Detection(Intent.chat, lang, c, q, confidence=0.8, reasons=["safety question"])
    has_place = bool(c.place)
    has_constraint = _has_constraint(c)
    only_grade = has_constraint and all(
        v is None for k, v in c.model_dump().items() if k in _CONSTRAINT_KEYS and k != "max_grade"
    )
    if (
        QUESTION.search(text)
        and not FIND_WORDS.search(text)
        and not has_place
        and (not has_constraint or only_grade)
    ):
        return Detection(
            Intent.chat,
            lang,
            c,
            QuestionKind.general if q is QuestionKind.none else q,
            confidence=0.7,
            reasons=["question without find words"],
        )
    if FIND_WORDS.search(text) or has_constraint or has_place:
        if has_place and (AROUND.search(text) or not has_constraint) and not c.region:
            reasons.append("place + around word")
            return Detection(Intent.around, lang, c, q, confidence=0.8, reasons=reasons)
        if has_constraint or c.region or FIND_WORDS.search(text):
            reasons.append("constraints/find words")
            return Detection(
                Intent.find if (has_constraint or c.region or not has_place) else Intent.around,
                lang,
                c,
                q,
                confidence=0.75,
                reasons=reasons,
            )
    if QUESTION.search(text):
        return Detection(
            Intent.chat,
            lang,
            c,
            QuestionKind.general if q is QuestionKind.none else q,
            confidence=0.6,
            reasons=["question"],
        )
    return Detection(Intent.chat, lang, c, q, confidence=0.4, reasons=["fallback"])


_CONSTRAINT_KEYS = (
    "max_ascent_m",
    "max_distance_km",
    "max_duration_min",
    "max_grade",
    "region",
    "origin",
    "max_travel_min",
    "hut",
    "dog",
    "kids",
    "loop",
    "bivouac",
)


def _has_constraint(c: Constraint) -> bool:
    return any(v is not None for k, v in c.model_dump().items() if k in _CONSTRAINT_KEYS)


def extract_constraints(text: str, lang: Lang, today: date) -> Constraint:
    c = Constraint(lang=lang, free_text=text)
    t = text
    low = t.lower()
    # region / canton
    m = CANTON_PREFIX.search(t)
    if m:
        code = _canton_code(m.group(2))
        if code:
            c.region = code
    if not c.region:
        for code, names in CANTON_NAMES.items():
            for n in names:
                if re.search(rf"\b{re.escape(n)}\b", low) and (
                    n not in ("bern", "basel", "zug", "jura", "uri", "schwyz", "glarus", "zürich", "zurich")
                    or re.search(r"\b(canton|kanton|cantone|in|im|dans le|nel|en)\s+" + re.escape(n), low)
                ):
                    c.region = code
                    break
            if c.region:
                break
    # place
    m = NEAR_PLACE.search(t)
    if m:
        cand = m.group(1).strip(" ,.?!")
        if cand.lower() not in ("i", "je", "ich", "io") and not any(
            cand.lower().startswith(w) for w in ("the ", "le ", "la ", "der ", "die ", "il ")
        ):
            c.place = cand
    # date
    c.date = _date_from_text(low, lang, today)
    # ascent
    m = ASCENT.search(t) or ASCENT2.search(t)
    if m:
        c.max_ascent_m = float(m.group(1))
    # distance
    m = DISTANCE.search(t)
    if m:
        c.max_distance_km = float(m.group(1).replace(",", "."))
    # travel time from origin
    m = TRAVEL.search(t)
    if m:
        c.max_travel_min = int(float(m.group(1).replace(",", ".")) * 60)
        c.origin = m.group(2).strip()
        c.transport_required = True
        if c.place and c.place.lower() == c.origin.lower():
            c.place = None
    else:
        m = DURATION.search(t)
        if m:
            c.max_duration_min = int(float(m.group(1).replace(",", ".")) * 60)
    if BY_TRANSPORT.search(t):
        c.transport_required = True
    m = GRADE.search(t)
    if m:
        c.max_grade = f"T{m.group(1)}"
    elif EASY.search(t):
        c.max_grade = "T2"
    if HUT.search(t):
        c.hut = True
    if DOG.search(t):
        c.dog = True
    if BIVOUAC.search(t):
        c.bivouac = True
    if WATER.search(t):
        c.water = True
    if LOOP.search(t):
        c.loop = True
    if KIDS.search(t):
        c.kids = True
    if SENIORS.search(t):
        c.seniors = True
    return c


def _canton_code(name: str) -> str | None:
    n = name.strip().lower().rstrip(".,!?")
    for code, names in CANTON_NAMES.items():
        if n == code or n in names or any(n.startswith(x) for x in names):
            return code
    return None


def _date_from_text(low: str, lang: Lang, today: date) -> str | None:
    m_iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", low)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))).isoformat()
        except ValueError:
            return None
    if re.search(r"\b(day after tomorrow|übermorgen|après-demain|dopodomani)\b", low):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"\b(tomorrow|morgen|demain|domani)\b", low):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\b(today|heute|aujourd'hui|oggi)\b", low):
        return today.isoformat()
    if re.search(r"\b(this weekend|weekend|wochenende|week-end|fine settimana)\b", low):
        days = (5 - today.weekday()) % 7
        return (today + timedelta(days=days or 7 if today.weekday() == 5 else days)).isoformat()
    for name, wd in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", low):
            days = (wd - today.weekday()) % 7 or 7
            return (today + timedelta(days=days)).isoformat()
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", low)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    for i, mn in enumerate(MONTHS[lang], 1):
        m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th|er|\.)?\s+(?:of\s+)?{mn}\b", low)
        if m:
            try:
                return date(today.year, i, int(m.group(1))).isoformat()
            except ValueError:
                return None
    return None


# ----- LLM extraction contract (standalone mode) -----
LLM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string", "enum": [i.value for i in Intent]},
        "lang": {"type": "string", "enum": ["en", "fr", "de", "it"]},
        "question": {"type": "string", "enum": [q.value for q in QuestionKind]},
        "selection": {"type": ["integer", "null"]},
        "constraints": Constraint.model_json_schema(),
    },
    "required": ["intent", "lang", "question", "selection", "constraints"],
}

LLM_PROMPT = (
    "Classify the user's message for a Swiss mountain-planning assistant. Intents: find (constraints → routes), "
    "around (routes near a place), audit (a route file is attached or named), check (single status: lift, hut, pass, "
    "road, fire ban), export (GPX/KML/GeoJSON), media (photos/stories), help, chat, emergency (injury, lost, accident), "
    "select (picks candidate 1–3), modify (changes a previous request). Extract constraints exactly as stated; never "
    "invent values. Dates are ISO; canton codes lower-case two letters. Reply language = language of the message."
)
