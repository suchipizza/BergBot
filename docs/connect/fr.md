# Connecter Telegram

Ton propre bot, sur ta machine. Rien n'est hébergé ; le jeton reste dans ~/.bergbot.

**Étape 1 — Créer un bot : ouvre @BotFather dans Telegram, envoie /newbot, choisis un nom et un identifiant, copie le jeton**

![](../screenshots/connect-tg-1.png)

**Étape 2 — Installer et connecter**
```
pipx install "bergbot[all]"
bergbot connect telegram
```
![](../screenshots/connect-tg-2.png)

**Étape 3 — Écris à ton bot : un lieu, une envie, ou envoie un GPX. Touche une suggestion pour commencer.**

![](../screenshots/connect-tg-3.png)

Optionnel : définis l'avatar dans @BotFather → /setuserpic avec brand/mascot/dist/avatar.png

## WhatsApp

En toute franchise : un bot WhatsApp Bergbot exige un compte business Meta, un numéro dédié et un webhook public ; ce sera une bêta hébergée (phase 3). Inscris-toi sur la liste d'attente. Aujourd'hui : Telegram, ou ton propre canal via ton agent.
