import asyncio
import logging
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "49"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Put it in .env")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("video-bot")

dp = Dispatcher()

URL_RE = re.compile(r"https?://\S+", re.I)

PLATFORMS = {
    "tiktok.com": "TikTok",
    "vm.tiktok.com": "TikTok",
    "instagram.com": "Instagram",
    "www.instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "www.youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "twitter.com": "X",
    "x.com": "X",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "reddit.com": "Reddit",
    "pinterest.com": "Pinterest",
    "vk.com": "VK",
}


def clean_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(").,]}>\"'")


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    for domain, name in PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "другая платформа"


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "video"


def progress_hook_factory(status_message: Message):
    last_update = {"t": 0.0, "percent": ""}

    def hook(d):
        if d.get("status") != "downloading":
            return

        now = time.monotonic()
        percent = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()

        if now - last_update["t"] < 2 and percent == last_update["percent"]:
            return

        last_update["t"] = now
        last_update["percent"] = percent

        text = f"⬇️ Скачивание: {percent or '?'}"
        if speed:
            text += f"\n⚡ Скорость: {speed}"
        if eta:
            text += f"\n⏱ ETA: {eta}"

        async def edit():
            try:
                await status_message.edit_text(text)
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(edit())
        except RuntimeError:
            pass

    return hook


def download_video(url: str, job_dir: Path, progress_hook):
    # Prefer the best available video + audio without transcoding.
    # yt-dlp/ffmpeg will only remux/merge streams when needed.
    output = str(job_dir / "%(title).120B.%(ext)s")

    opts = {
        "format": "bv*+ba/b",
        "outtmpl": output,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "continuedl": True,
        "overwrites": False,
        "progress_hooks": [progress_hook],
        # Do not use postprocessors that re-encode video.
        "postprocessors": [],
    }

    # Prefer MP4-compatible streams where available, but fall back to best.
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = info.get("requested_downloads") or []
            title = info.get("title") or "video"
            duration = info.get("duration")
            width = info.get("width")
            height = info.get("height")
            fps = info.get("fps")
            filesize = info.get("filesize") or info.get("filesize_approx")

        candidates = [p for p in job_dir.iterdir() if p.is_file()]
        if not candidates:
            raise RuntimeError("yt-dlp completed but no output file was found.")

        # Prefer the largest media file; metadata sidecars are ignored.
        media = [
            p for p in candidates
            if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
        ]
        final = max(media or candidates, key=lambda p: p.stat().st_size)

        return {
            "path": final,
            "title": title,
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "filesize": filesize,
        }
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(str(e)) from e


async def process_url(message: Message, url: str):
    platform = detect_platform(url)
    status = await message.answer(
        f"🔎 Платформа: {platform}\n"
        "Проверяю доступное качество и начинаю загрузку..."
    )

    job_dir = DOWNLOAD_DIR / f"{message.chat.id}_{int(time.time()*1000)}"
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = await asyncio.to_thread(
            download_video,
            url,
            job_dir,
            progress_hook_factory(status),
        )

        path = result["path"]
        size = path.stat().st_size

        if size > MAX_FILE_BYTES:
            await status.edit_text(
                f"⚠️ Файл скачан, но его размер {size/1024/1024:.1f} MB "
                f"выше лимита бота {MAX_FILE_MB} MB.\n"
                "Сжатие не выполняю, чтобы не ухудшать качество."
            )
            return

        resolution = ""
        if result["width"] and result["height"]:
            resolution = f"{result['width']}×{result['height']}"
        fps = f"{result['fps']:.0f} FPS" if result["fps"] else ""

        caption = (
            f"✅ Готово\n"
            f"🎬 {safe_name(result['title'])}\n"
            f"📐 {resolution or 'неизвестно'}"
            f"{(' • ' + fps) if fps else ''}\n"
            f"📦 {size/1024/1024:.1f} MB\n"
            f"🚫 Повторного видеокодирования не выполнялось"
        )

        await status.edit_text("📤 Отправляю файл без повторного сжатия...")

        # Sending as document avoids Telegram's video-processing path as much as possible.
        await message.answer_document(
            document=FSInputFile(path),
            caption=caption[:1024],
        )

        try:
            await status.delete()
        except Exception:
            pass

    except Exception as e:
        log.exception("Download failed")
        msg = str(e)
        if len(msg) > 800:
            msg = msg[-800:]
        try:
            await status.edit_text(
                "❌ Не удалось скачать видео.\n\n"
                f"{msg}\n\n"
                "Проверь, что ссылка публичная и доступна без авторизации."
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Я скачиваю видео по ссылке.\n\n"
        "Отправь ссылку на TikTok, Instagram, YouTube, X, Facebook, "
        "Reddit, Pinterest, VK или другую поддерживаемую платформу.\n\n"
        "🎯 Приоритет: максимально доступное качество.\n"
        "🚫 Я не перекодирую видео повторно.\n"
        "📦 Файл отправляется как документ, чтобы избежать лишней обработки Telegram.\n\n"
        "Важно: отсутствие водяного знака возможно только если источник "
        "предоставляет соответствующую версию видео."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Просто отправь мне URL видео.\n\n"
        "Пример:\n"
        "https://www.tiktok.com/...\n\n"
        "Бот выберет лучший доступный поток и объединит видео+аудио "
        "без повторного кодирования."
    )


@dp.message(F.text)
async def url_handler(message: Message):
    url = clean_url(message.text or "")
    if not url:
        await message.answer("Отправь ссылку на видео.")
        return
    await process_url(message, url)


async def main():
    bot = Bot(BOT_TOKEN)
    log.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
