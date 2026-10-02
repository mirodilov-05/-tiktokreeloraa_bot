# TikTokReeloraa Bot

Telegram downloader MVP based on:

- Python
- aiogram 3
- yt-dlp
- FFmpeg
- .env for the BotFather token

## 1. Security

The token previously pasted into chat must be considered exposed.

Open @BotFather, select the bot, use `/revoke`, then generate a new token.
Put the new token only into `.env`.

Never commit `.env` to GitHub.

## 2. Install

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Install FFmpeg and make sure `ffmpeg` is available in PATH:

```powershell
ffmpeg -version
```

## 3. Configure

Copy:

```text
.env.example -> .env
```

Then put your NEW BotFather token into:

```env
BOT_TOKEN=...
```

## 4. Run

```powershell
python bot.py
```

Open your bot in Telegram and send a public video URL.

## 5. Quality behavior

The bot requests:

```text
best video + best audio
```

and uses FFmpeg only when it needs to merge/remux streams. It does not intentionally re-encode the video.

This means it preserves the downloaded stream's resolution/bitrate/codec as far as the source and container allow.

It cannot recover quality that the social network does not provide.

## 6. Watermarks

The bot does not add its own watermark.

A watermark that is already burned into the source cannot be removed simply by downloading the file. The bot only uses a watermark-free source when the platform/source makes such a version available through the supported downloader.

## 7. Telegram size

The default limit is 49 MB to stay below common cloud Bot API upload constraints.

For larger files, the next production step is a Telegram Local Bot API server or an external storage/download link workflow.
