# TikTokReeloraa / Cinematch — Ready Telegram Downloader

The original Next.js/Cinematch application is preserved. A new independent Telegram downloader service is in `telegram-bot/`.

## Start downloader

```powershell
cd telegram-bot
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# put NEW BotFather token into .env
python bot.py
```

The web application remains available through the existing Next.js scripts.
