# Installare Bergbot

Un comando per superficie. Ogni guida ha uno screenshot per passo; sul sito i comandi hanno un pulsante copia.

## Claude Code

**Passo 1 — Aggiungi il marketplace**
```
/plugin marketplace add suchipizza/BergBot
```
![](../screenshots/install-cc-1.png)

**Passo 2 — Installa il plugin**
```
/plugin install bergbot
```
![](../screenshots/install-cc-2.png)

**Passo 3 — Installa la CLI che il plugin chiama, poi scrivi una frase o /find …**
```
pipx install bergbot
```
![](../screenshots/install-cc-3.png)

## Claude.ai

Si installa da Personalizza → Plugin → Aggiungi marketplace → `https://github.com/suchipizza/BergBot`. Verificato il 09.09.2026: l'installazione funziona, ma claude.ai esegue le skill in una sandbox che blocca le fonti svizzere (GeoAdmin, SvizzeraMobile, MeteoSvizzera, trasporti). Bergbot non può controllare nulla e lo dice («impossibile verificare»). Per controlli veri: Claude Code, Telegram o CLI; claude.ai può mostrare un `audit.json` prodotto localmente.

## CLI

**Passo 1 — Installa**
```
pipx install "bergbot[all]"
bergbot doctor
```
**Passo 2 — Facoltativo: la tua chiave Anthropic attiva la verifica web e la chat libera**
```
export ANTHROPIC_API_KEY=sk-ant-…
```
**Passo 3 — Chatta, o lancia un controllo**
```
bergbot chat
bergbot audit route.gpx --date 2026-09-12 --lang it --out audit.json && bergbot render audit.json
```
![](../screenshots/chat.png)

## Il tuo canale (WhatsApp, Signal, iMessage…)

Se il tuo agente è già collegato a un'app di messaggistica tramite un server MCP o un bridge, installa il plugin Claude Code e scrivi al tuo agente da quell'app. Bergbot non fornisce bridge e non consiglia bridge WhatsApp non ufficiali (violano i termini di WhatsApp).
