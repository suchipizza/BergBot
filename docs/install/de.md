# Bergbot installieren

Ein Befehl pro Oberfläche. Jede Anleitung hat einen Screenshot pro Schritt; auf der Website haben Befehle einen Kopierknopf.

## Claude Code

**Schritt 1 — Marketplace hinzufügen**
```
/plugin marketplace add suchipizza/BergBot
```
![](../screenshots/install-cc-1.png)

**Schritt 2 — Plugin installieren**
```
/plugin install bergbot
```
![](../screenshots/install-cc-2.png)

**Schritt 3 — Die CLI installieren, die das Plugin aufruft, dann einen Satz tippen oder /find …**
```
pipx install bergbot
```
![](../screenshots/install-cc-3.png)

## Claude.ai

Bald — der Weg Anpassen → Plugins → Marketplace hinzufügen wird gerade von einem frischen Konto aus geprüft. Bis dahin: Claude Code, Telegram oder CLI.

## CLI

**Schritt 1 — Installieren**
```
pipx install "bergbot[all]"
bergbot doctor
```
**Schritt 2 — Optional: dein Anthropic-Schlüssel aktiviert Web-Prüfung und freies Chatten**
```
export ANTHROPIC_API_KEY=sk-ant-…
```
**Schritt 3 — Chatten oder eine Prüfung starten**
```
bergbot chat
bergbot audit route.gpx --date 2026-09-12 --lang de --out audit.json && bergbot render audit.json
```
![](../screenshots/chat.png)

## Eigener Kanal (WhatsApp, Signal, iMessage…)

Ist dein Agent schon über einen MCP-Server oder eine Brücke mit einer Messaging-App verbunden, installiere das Claude-Code-Plugin und schreib deinem Agenten aus dieser App. Bergbot liefert keine Brücke und empfiehlt keine inoffiziellen WhatsApp-Brücken (sie verstossen gegen die WhatsApp-Bedingungen).
