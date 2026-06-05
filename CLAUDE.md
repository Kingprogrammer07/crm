# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-file Telegram bot (`main.py`) that registers leads. Flow: user `/start` → bot asks
name → asks phone → creates a **contact + lead in amoCRM** → sends a promo post (photo +
HTML caption). Bot-facing text is **Uzbek**; keep new user-facing strings in Uzbek.

## Commands

```powershell
# install deps (.venv already present)
.venv\Scripts\pip install -r requirements.txt

# run locally (needs .env populated)
.venv\Scripts\python main.py
```

No tests, no linter, no build step.

### Deployment (AWS EC2 Ubuntu, systemd)

Production runs under systemd unit `crm_bot.service` in **polling mode** (not webhook).
On the server:
```bash
sudo systemctl restart crm_bot
journalctl -u crm_bot -f      # live logs
```

## Architecture

- **`create_lead_with_contact()`** — the only non-trivial unit. Two sequential amoCRM v4
  REST calls over one `aiohttp` session: POST `/contacts` (name + `PHONE` custom field),
  then POST `/leads` linking the returned `contact_id` via `_embedded.contacts`. Returns
  `lead_id`. Base URL is hardcoded to `.amocrm.ru`.
- **FSM** — `Royxat` StatesGroup (`ism`, `telefon`) drives the two-step registration via
  aiogram `MemoryStorage`. Memory storage means **in-flight conversations reset on restart**.
- amoCRM failure is caught and logged but **non-fatal**: the user still gets the confirmation
  + promo post even if the lead wasn't created. Don't make amoCRM errors block the user reply.

## Config & gotchas

- Required `.env` vars (validated at startup, raise `ValueError` if missing): `BOT_TOKEN`,
  `AMOCRM_DOMAIN` (subdomain only, no `.amocrm.ru`), `AMOCRM_ACCESS_TOKEN`. Optional:
  `AMOCRM_PIPELINE_ID` (int). See `.env.example`. `.env` is gitignored — never commit it.
- `PHOTO_FILE_ID` is a hardcoded Telegram file_id; valid only for the bot that originally
  uploaded it. A new bot token invalidates it — re-upload to get a fresh id.
- **aiogram ≥ 3.7**: `parse_mode` cannot be passed to `Bot()`. Use
  `Bot(token=..., default=DefaultBotProperties(parse_mode="HTML"))` (already done). This was
  a prior production crash-loop — don't regress it.
