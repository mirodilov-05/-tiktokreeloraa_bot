# Telegram Media Downloader

This service is the production-oriented downloader layer for the Cinematch project.

## Features

- TikTok, Instagram, YouTube, X, Facebook, Reddit, Pinterest, VK and other yt-dlp-supported public URLs.
- Best available video + audio.
- No intentional video re-encoding.
- FFmpeg only for merging/remuxing when required.
- Sends as a Telegram document to reduce additional media processing.
- Progress updates.
- Optional output formats: YouTube Shorts (1080x1920), standard video (1920x1080), or original size.
- SQLite cache to avoid downloading the same URL repeatedly.
- Concurrent-job limit.
- Automatic cleanup of old temporary jobs.
- No watermark is added by the bot.

Resizing uses FFmpeg with center cropping and H.264/AAC encoding. The original option keeps the
source dimensions and avoids video re-encoding.

## Important

The bot does not remove a watermark already burned into a source video. It also does not bypass login/private-content restrictions.

## Run on Windows

```powershell
cd telegram-bot
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put a fresh BotFather token into `.env` and make sure FFmpeg is installed:

```powershell
ffmpeg -version
python bot.py
```

## Docker

```powershell
copy .env.example .env
# edit .env
docker build -t tiktokreeloraa-bot .
docker run --rm --env-file .env -v "${PWD}/downloads:/app/downloads" -v "${PWD}/data:/app/data" tiktokreeloraa-bot
```

For a hosting platform, add `BOT_TOKEN` (or `TELEGRAM_BOT_TOKEN`) in the service's
Environment/Secrets settings. Do not commit `.env` and do not put the token in the Dockerfile.

## Telegram size

The default upload target is 49 MB. Larger files are deliberately not transcoded down just to fit. For larger production files, deploy Telegram Local Bot API or add object-storage links in the next stage.
