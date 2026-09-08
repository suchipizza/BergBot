"""Static website generator: four languages, pages Home · Install · Connect · Examples · Coverage · Safety & sources ·
Roadmap · Waitlist. Output in website/dist/ (GitHub Pages). No JS required; a tiny inline script handles language
auto-detect and copy buttons. Coverage is generated from `bergbot doctor --json` when available (else last results)."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.config import settings, utm  # noqa: E402
from bergbot.i18n import LANGS, load  # noqa: E402

OUT = ROOT / "website" / "dist"
S = settings()

T = {
    "en": dict(
        nav=["Home", "Install", "Connect", "Examples", "Coverage", "Safety & sources", "Roadmap", "Waitlist"],
        tagline="Check everything before you go to the mountains.",
        promise="Tell Bergbot where you want to go. It checks the weather, the trail, the hazards, the train — and hands you the route.",
        install="Install",
        connect="Connect Telegram",
        star="★ Star on GitHub",
        how="How it works",
        how_items=[
            "Write one sentence in EN, FR, DE or IT — or send a GPX.",
            "Bergbot checks official Swiss data and the live web: closures, weather, wind, fire, quiet zones, shooting, guardian dogs, transport, lifts, huts.",
            "Warnings first, ≤ 12 lines, then a self-contained report and a GPX for swisstopo.",
            "Runs on your machine and your AI subscription. Nothing hosted, nothing phoned home.",
        ],
        examples="Examples",
        examples_intro="Real, regenerable outputs. Open a report on your phone.",
        coverage="Coverage",
        coverage_intro="Sources behind every audit, their licence and freshness. Generated from `bergbot doctor`.",
        safety="Safety & sources",
        safety_body=[
            "Bergbot informs. The decision is yours. Warnings always come first.",
            "Unverified stays unverified: a timetable is not a running lift, silence is not an open hut.",
            "No route is synthesised off the official network.",
            'The register (playful/serious) is decided by rule; the words "safe" and equivalents are banned by test in every language.',
            "Every finding carries an evidence class (A official · B derived · C forecast · D interpretation · E judgment required), a source and timestamps, with the original wording beside the translation.",
            "Emergency? Bergbot answers only: 1414 (Rega) or 112, share your position, stay put.",
        ],
        roadmap="Roadmap",
        waitlist="Waitlist",
        waitlist_body='Hosted WhatsApp, monitoring ("tell me when the lift reopens"), guides & huts — tell us what you\'d want. No promises, no spam.',
        waitlist_cta="Join the waitlist",
        open_report="Open report",
        prompt="Prompt",
        reply="Reply",
        source="Source",
        licence="Licence",
        ttl="Freshness",
        status="Status",
        lang_name="English",
    ),
    "fr": dict(
        nav=[
            "Accueil",
            "Installer",
            "Connecter",
            "Exemples",
            "Couverture",
            "Sécurité & sources",
            "Feuille de route",
            "Liste d'attente",
        ],
        tagline="Vérifie tout avant d'aller en montagne.",
        promise="Dis à Bergbot où tu veux aller. Il vérifie la météo, le sentier, les dangers, le train — et te donne l'itinéraire.",
        install="Installer",
        connect="Connecter Telegram",
        star="★ Star sur GitHub",
        how="Comment ça marche",
        how_items=[
            "Écris une phrase en FR, DE, IT ou EN — ou envoie un GPX.",
            "Bergbot contrôle les données officielles suisses et le web en direct : fermetures, météo, vent, feu, zones de tranquillité, tirs, chiens de protection, transports, remontées, cabanes.",
            "Avertissements d'abord, ≤ 12 lignes, puis un rapport autonome et un GPX pour swisstopo.",
            "Tourne sur ta machine et ton abonnement IA. Rien d'hébergé, rien de transmis.",
        ],
        examples="Exemples",
        examples_intro="Résultats réels, régénérables. Ouvre un rapport sur ton téléphone.",
        coverage="Couverture",
        coverage_intro="Les sources derrière chaque contrôle, leur licence et leur fraîcheur. Généré par `bergbot doctor`.",
        safety="Sécurité & sources",
        safety_body=[
            "Bergbot informe. La décision t'appartient. Les avertissements viennent toujours en premier.",
            "Non vérifié reste non vérifié : un horaire n'est pas une remontée en service, le silence n'est pas une cabane ouverte.",
            "Aucun itinéraire n'est inventé hors du réseau officiel.",
            "Le registre (enjoué/sérieux) est décidé par règle ; les mots « sans danger » et équivalents sont interdits par test dans chaque langue.",
            "Chaque constat porte une classe de preuve (A officiel · B dérivé · C prévision · D interprétation · E jugement requis), une source et des horodatages, avec le texte original à côté de la traduction.",
            "Urgence ? Bergbot répond seulement : 1414 (Rega) ou 112, transmets ta position, reste sur place.",
        ],
        roadmap="Feuille de route",
        waitlist="Liste d'attente",
        waitlist_body="WhatsApp hébergé, surveillance (« préviens-moi quand la remontée rouvre »), guides & cabanes — dis-nous ce que tu voudrais. Sans promesse, sans spam.",
        waitlist_cta="Rejoindre la liste d'attente",
        open_report="Ouvrir le rapport",
        prompt="Demande",
        reply="Réponse",
        source="Source",
        licence="Licence",
        ttl="Fraîcheur",
        status="État",
        lang_name="Français",
    ),
    "de": dict(
        nav=[
            "Start",
            "Installieren",
            "Verbinden",
            "Beispiele",
            "Abdeckung",
            "Sicherheit & Quellen",
            "Roadmap",
            "Warteliste",
        ],
        tagline="Prüf alles, bevor du in die Berge gehst.",
        promise="Sag Bergbot, wohin du willst. Er prüft Wetter, Weg, Gefahren und Zug — und gibt dir die Route.",
        install="Installieren",
        connect="Telegram verbinden",
        star="★ Auf GitHub sternen",
        how="So funktioniert es",
        how_items=[
            "Schreib einen Satz auf DE, FR, IT oder EN — oder schick ein GPX.",
            "Bergbot prüft offizielle Schweizer Daten und das Live-Web: Sperrungen, Wetter, Wind, Feuer, Wildruhezonen, Schiessbetrieb, Herdenschutzhunde, ÖV, Bahnen, Hütten.",
            "Warnungen zuerst, ≤ 12 Zeilen, dann ein eigenständiger Bericht und ein GPX für swisstopo.",
            "Läuft auf deinem Rechner mit deinem KI-Abo. Nichts gehostet, nichts nach Hause telefoniert.",
        ],
        examples="Beispiele",
        examples_intro="Echte, reproduzierbare Ergebnisse. Öffne einen Bericht auf dem Handy.",
        coverage="Abdeckung",
        coverage_intro="Die Quellen hinter jeder Prüfung, ihre Lizenz und Aktualität. Erzeugt aus `bergbot doctor`.",
        safety="Sicherheit & Quellen",
        safety_body=[
            "Bergbot informiert. Die Entscheidung liegt bei dir. Warnungen kommen immer zuerst.",
            "Ungeprüft bleibt ungeprüft: ein Fahrplan ist keine fahrende Bahn, Schweigen ist keine offene Hütte.",
            "Keine Route wird ausserhalb des offiziellen Netzes erfunden.",
            "Das Register (verspielt/ernst) wird nach Regel entschieden; das Wort „sicher“ und Entsprechungen sind in jeder Sprache per Test verboten.",
            "Jeder Befund trägt eine Belegklasse (A offiziell · B abgeleitet · C Prognose · D Interpretation · E eigenes Urteil), eine Quelle und Zeitstempel, mit dem Originaltext neben der Übersetzung.",
            "Notfall? Bergbot antwortet nur: 1414 (Rega) oder 112, Position teilen, bleiben, wo du bist.",
        ],
        roadmap="Roadmap",
        waitlist="Warteliste",
        waitlist_body="Gehostetes WhatsApp, Überwachung („sag mir, wenn die Bahn wieder fährt“), Guides & Hütten — sag uns, was du willst. Keine Versprechen, kein Spam.",
        waitlist_cta="Auf die Warteliste",
        open_report="Bericht öffnen",
        prompt="Anfrage",
        reply="Antwort",
        source="Quelle",
        licence="Lizenz",
        ttl="Aktualität",
        status="Status",
        lang_name="Deutsch",
    ),
    "it": dict(
        nav=[
            "Home",
            "Installare",
            "Collegare",
            "Esempi",
            "Copertura",
            "Sicurezza & fonti",
            "Roadmap",
            "Lista d'attesa",
        ],
        tagline="Controlla tutto prima di andare in montagna.",
        promise="Di' a Bergbot dove vuoi andare. Controlla meteo, sentiero, pericoli e treno — e ti consegna l'itinerario.",
        install="Installa",
        connect="Collega Telegram",
        star="★ Star su GitHub",
        how="Come funziona",
        how_items=[
            "Scrivi una frase in IT, FR, DE o EN — o invia un GPX.",
            "Bergbot controlla i dati ufficiali svizzeri e il web in diretta: chiusure, meteo, vento, fuoco, zone di tranquillità, tiri, cani da protezione, mezzi, impianti, capanne.",
            "Avvisi per primi, ≤ 12 righe, poi un rapporto autonomo e un GPX per swisstopo.",
            "Gira sulla tua macchina con il tuo abbonamento IA. Nulla ospitato, nulla trasmesso.",
        ],
        examples="Esempi",
        examples_intro="Risultati reali e rigenerabili. Apri un rapporto sul telefono.",
        coverage="Copertura",
        coverage_intro="Le fonti dietro ogni controllo, licenza e freschezza. Generato da `bergbot doctor`.",
        safety="Sicurezza & fonti",
        safety_body=[
            "Bergbot informa. La decisione è tua. Gli avvisi vengono sempre per primi.",
            "Non verificato resta non verificato: un orario non è un impianto in funzione, il silenzio non è una capanna aperta.",
            "Nessun itinerario è inventato fuori dalla rete ufficiale.",
            "Il registro (giocoso/serio) è deciso per regola; la parola « sicuro » e gli equivalenti sono vietati per test in ogni lingua.",
            "Ogni riscontro porta una classe di prova (A ufficiale · B derivato · C previsione · D interpretazione · E giudizio necessario), una fonte e timestamp, con il testo originale accanto alla traduzione.",
            "Emergenza? Bergbot risponde solo: 1414 (Rega) o 112, condividi la posizione, resta dove sei.",
        ],
        roadmap="Roadmap",
        waitlist="Lista d'attesa",
        waitlist_body="WhatsApp ospitato, monitoraggio (« avvisami quando riapre l'impianto »), guide & capanne — dicci cosa vorresti. Nessuna promessa, niente spam.",
        waitlist_cta="Iscriviti alla lista d'attesa",
        open_report="Apri il rapporto",
        prompt="Richiesta",
        reply="Risposta",
        source="Fonte",
        licence="Licenza",
        ttl="Freschezza",
        status="Stato",
        lang_name="Italiano",
    ),
}
PAGES = ["index", "install", "connect", "examples", "coverage", "safety", "roadmap", "waitlist"]

CSS = """
:root{--ink:#1c2430;--muted:#5b6b7b;--line:#e3e8ee;--soft:#f4f6f9;--red:#c8102e;--link:#1f6feb}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}
header{border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:12px 0;font-size:.95rem}nav a{color:var(--ink);text-decoration:none;padding:4px 6px;border-radius:6px}nav a.active,nav a:hover{background:var(--soft)}
nav .brand{font-weight:800;margin-right:6px;display:flex;align-items:center;gap:8px}nav .brand img{width:28px;height:28px}
.langs{margin-left:auto;display:flex;gap:6px}.langs a{font-size:.8rem;padding:2px 6px;border:1px solid var(--line);border-radius:6px}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:center;padding:44px 0}
.hero h1{font-size:2.2rem;line-height:1.15;margin:0 0 10px}.hero p.lead{font-size:1.15rem;color:var(--muted)}
.cta a{display:inline-block;margin:6px 8px 6px 0;padding:10px 16px;border-radius:10px;background:var(--soft);border:1px solid var(--line);text-decoration:none;color:var(--ink);font-weight:600}.cta a.primary{background:var(--red);color:#fff;border-color:var(--red)}
.mascot{max-width:260px;width:100%;display:block;margin:0 auto}
.shots{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;padding:10px 0 30px}.shots img{max-width:100%;border:1px solid var(--line);border-radius:12px}
.shots .phone{width:240px}.shots .chat{width:460px}
h2{margin-top:36px;border-bottom:2px solid var(--line);padding-bottom:6px}
pre{background:#0f172a;color:#e5eaf0;padding:12px 14px;border-radius:10px;overflow-x:auto;position:relative}
pre button{position:absolute;right:8px;top:8px;font-size:.75rem;padding:3px 8px;border-radius:6px;border:1px solid #475569;background:#1e293b;color:#e5eaf0;cursor:pointer}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0}.tabs a{padding:6px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink)}.tabs a.active{background:var(--soft);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}
.ok{color:#2b8a3e;font-weight:700}.fail{color:var(--red);font-weight:700}
.card{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:12px 0}
footer{margin-top:50px;padding:20px 0;border-top:1px solid var(--line);color:var(--muted);font-size:.9rem}
.step img{max-width:100%;border:1px solid var(--line);border-radius:10px;margin:6px 0 14px}
@media(max-width:720px){.hero{grid-template-columns:1fr}.hero h1{font-size:1.7rem}}
"""
JS = """
document.querySelectorAll('pre').forEach(function(p){var b=document.createElement('button');b.textContent='copy';b.onclick=function(){navigator.clipboard.writeText(p.innerText.replace(/^copy\\n?/,'').trim());b.textContent='✓';setTimeout(function(){b.textContent='copy'},1200)};p.appendChild(b)});
(function(){if(location.pathname.split('/').filter(Boolean).length<=1&&!localStorage.getItem('bb_lang')){var l=(navigator.language||'en').slice(0,2);if(['fr','de','it'].indexOf(l)>=0&&location.pathname.indexOf('/'+l+'/')<0){localStorage.setItem('bb_lang',l);location.href=l+'/';}}})();
document.querySelectorAll('.langs a').forEach(function(a){a.onclick=function(){localStorage.setItem('bb_lang',a.dataset.lang)}});
"""


def nav(lang: str, page: str) -> str:
    t = T[lang]
    items = "".join(
        f'<a href="{p if p != "index" else "."}{"" if p == "index" else ".html"}" class="{"active" if p == page else ""}">{label}</a>'
        for p, label in zip(PAGES, t["nav"], strict=True)
    )
    langs = "".join(
        f'<a href="../{lg}/{page if page != "index" else ""}{".html" if page != "index" else ""}" data-lang="{lg}">{lg.upper()}</a>'
        for lg in LANGS
    )
    logo = (
        base64.b64encode((ROOT / "brand" / "mascot" / "dist" / "default.webp").read_bytes()).decode()
        if (ROOT / "brand" / "mascot" / "dist" / "default.webp").exists()
        else ""
    )
    img = f'<img src="data:image/webp;base64,{logo}" alt="">' if logo else ""
    return f'<header><div class="wrap"><nav><span class="brand">{img}Bergbot</span>{items}<span class="langs">{langs}</span></nav></div></header>'


def page(lang: str, name: str, body: str, title: str) -> str:
    return f"""<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Bergbot</title><meta name="description" content="{T[lang]["tagline"]}"><style>{CSS}</style></head><body>{nav(lang, name)}<main class="wrap">{body}</main><footer><div class="wrap">Bergbot · MIT · <a href="{S["github_url"]}">GitHub</a> · Map data © swisstopo · © BAFU · © VBS · © ASTRA/SchweizMobil · © MeteoSchweiz · © OpenStreetMap contributors</div></footer><script>{JS}</script></body></html>"""


def home(lang: str) -> str:
    t = T[lang]
    mascot = "../assets/hero.png"
    how = "".join(f"<li>{x}</li>" for x in t["how_items"])
    return f"""<section class="hero"><div><h1>{t["tagline"]}</h1><p class="lead">{t["promise"]}</p>
<p class="cta"><a class="primary" href="install.html">{t["install"]}</a><a href="connect.html">{t["connect"]}</a><a href="{utm(S["github_url"], "website", "web")}">{t["star"]}</a></p></div>
<div><img class="mascot" src="{mascot}" alt="Bergbot"></div></section>
<div class="shots"><img class="phone" src="../assets/report-phone.png" alt="report"><img class="chat" src="../assets/chat.png" alt="chat"></div>
<h2>{t["how"]}</h2><ol>{how}</ol>"""


def md_to_html(md: str) -> str:
    """Tiny markdown subset for the guides: headings, bold lines, code fences, images, paragraphs."""
    out: list[str] = []
    in_code = False
    for line in md.splitlines():
        if line.startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line.replace("&", "&amp;").replace("<", "&lt;"))
            continue
        if line.startswith("# "):
            out.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("![]("):
            src = line[4:-1].replace("../screenshots/", "../assets/")
            out.append(f'<div class="step"><img src="{src}" alt=""></div>')
        elif line.startswith("**") and line.endswith("**"):
            out.append(f"<p><strong>{line.strip('*')}</strong></p>")
        elif line.strip():
            out.append(f"<p>{line}</p>")
    return "\n".join(out)


def examples(lang: str) -> str:
    t = T[lang]
    cards = []
    for d in sorted((ROOT / "examples").iterdir()):
        if not (d / "report.html").exists():
            continue
        prompt = (
            (d / "prompt.txt").read_text(encoding="utf-8").strip().splitlines()[0]
            if (d / "prompt.txt").exists()
            else d.name
        )
        msg = (d / "message.txt").read_text(encoding="utf-8") if (d / "message.txt").exists() else ""
        reply = msg.split("\n> ")[-1].split("\n", 1)[-1].strip() if msg else ""
        cards.append(
            f'<div class="card"><h3>{d.name}</h3><p><strong>{t["prompt"]}:</strong> {prompt}</p><pre>{reply.replace("&", "&amp;").replace("<", "&lt;")}</pre><p><a href="../examples/{d.name}/report.html">{t["open_report"]}</a> · <a href="../examples/{d.name}/route.gpx">GPX</a></p></div>'
        )
    return f"<h1>{t['examples']}</h1><p>{t['examples_intro']}</p>" + "".join(cards)


def coverage(lang: str) -> str:
    t = T[lang]
    rows = []
    try:
        doc = json.loads(
            subprocess.run(
                [sys.executable, "-m", "bergbot.cli", "doctor", "--json"],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            ).stdout
        )
        adapters = doc.get("adapters", [])
    except Exception:  # noqa: BLE001
        adapters = []
    for a in adapters:
        ttl = a.get("ttl_s") or 0
        fresh = "live" if ttl < 3600 else f"{ttl // 3600} h" if ttl < 86400 else f"{ttl // 86400} d"
        rows.append(
            f'<tr><td>{a["id"]}</td><td class="{"ok" if a.get("ok") else "fail"}">{"✔" if a.get("ok") else "✘"}</td><td>{a.get("licence", "")}</td><td>{fresh}</td></tr>'
        )
    return f"<h1>{t['coverage']}</h1><p>{t['coverage_intro']}</p><table><thead><tr><th>{t['source']}</th><th>{t['status']}</th><th>{t['licence']}</th><th>{t['ttl']}</th></tr></thead><tbody>{''.join(rows)}</tbody></table><p><a href='../data-licences.html'>docs/data-licences.md</a></p>"


def safety(lang: str) -> str:
    t = T[lang]
    return (
        f"<h1>{t['safety']}</h1>"
        + "".join(f"<p>{x}</p>" for x in t["safety_body"])
        + f"<p><a href='{S['github_url']}/blob/main/docs/data-licences.md'>Sources & licences</a> · <a href='{S['github_url']}/blob/main/docs/BERGBOT_PRD.md'>PRD §7</a></p>"
    )


def roadmap(lang: str) -> str:
    md = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    html = (
        "<table>"
        + "".join(
            ("<tr>" + "".join(f"<td>{c.strip()}</td>" for c in r.strip("|").split("|")) + "</tr>")
            for r in rows
            if not set(r) <= set("|- ")
        )
        + "</table>"
    )
    return f"<h1>{T[lang]['roadmap']}</h1>{html}"


def waitlist(lang: str) -> str:
    t = T[lang]
    return f"<h1>{t['waitlist']}</h1><p>{t['waitlist_body']}</p><p class='cta'><a class='primary' href='{utm(S['waitlist_url'], 'website', 'web')}'>{t['waitlist_cta']}</a></p>"


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for f in (ROOT / "docs" / "screenshots").glob("*.png"):
        shutil.copy(f, OUT / "assets" / f.name)
    hero = ROOT / "brand" / "mascot" / "dist" / "default-512.png"
    if hero.exists():
        shutil.copy(hero, OUT / "assets" / "hero.png")
    for d in (ROOT / "examples").iterdir():
        if (d / "report.html").exists():
            (OUT / "examples" / d.name).mkdir(parents=True, exist_ok=True)
            for f in ("report.html", "route.gpx", "message.txt", "prompt.txt"):
                if (d / f).exists():
                    shutil.copy(d / f, OUT / "examples" / d.name / f)
    (OUT / "data-licences.html").write_text(
        page(
            "en",
            "coverage",
            md_to_html((ROOT / "docs" / "data-licences.md").read_text(encoding="utf-8")).replace(
                "<p>|", "<p style='font-family:monospace;font-size:.8rem'>|"
            ),
            "Data licences",
        ),
        encoding="utf-8",
    )
    for lang in LANGS:
        d = OUT / lang
        d.mkdir(exist_ok=True)
        t = T[lang]
        (d / "index.html").write_text(page(lang, "index", home(lang), t["tagline"]), encoding="utf-8")
        (d / "install.html").write_text(
            page(
                lang,
                "install",
                md_to_html((ROOT / "docs" / "install" / f"{lang}.md").read_text(encoding="utf-8")),
                t["nav"][1],
            ),
            encoding="utf-8",
        )
        (d / "connect.html").write_text(
            page(
                lang,
                "connect",
                md_to_html((ROOT / "docs" / "connect" / f"{lang}.md").read_text(encoding="utf-8")),
                t["nav"][2],
            ),
            encoding="utf-8",
        )
        (d / "examples.html").write_text(
            page(lang, "examples", examples(lang), t["examples"]), encoding="utf-8"
        )
        (d / "coverage.html").write_text(
            page(lang, "coverage", coverage(lang), t["coverage"]), encoding="utf-8"
        )
        (d / "safety.html").write_text(page(lang, "safety", safety(lang), t["safety"]), encoding="utf-8")
        (d / "roadmap.html").write_text(page(lang, "roadmap", roadmap(lang), t["roadmap"]), encoding="utf-8")
        (d / "waitlist.html").write_text(
            page(lang, "waitlist", waitlist(lang), t["waitlist"]), encoding="utf-8"
        )
    (OUT / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=en/"><script>var l=(navigator.language||"en").slice(0,2);var s=localStorage.getItem("bb_lang");l=s||l;location.replace((["fr","de","it"].indexOf(l)>=0?l:"en")+"/");</script></head><body><a href="en/">Bergbot</a></body></html>',
        encoding="utf-8",
    )
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    fixed = load("en").t("safety.fixed_line")
    print(
        f"website built in {OUT} — {sum(1 for _ in OUT.rglob('*.html'))} pages; safety page carries no mascot; fixed line: {fixed}"
    )


if __name__ == "__main__":
    build()
