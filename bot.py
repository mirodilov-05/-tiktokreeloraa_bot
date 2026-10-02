import asyncio
import hashlib
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
DB_PATH = Path(os.getenv("DB_PATH", "./data/bot.db"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "49"))
MAX_CONCURRENT = max(1, int(os.getenv("MAX_CONCURRENT", "2")))
JOB_TTL_HOURS = max(1, int(os.getenv("JOB_TTL_HOURS", "6")))
REQUEST_TIMEOUT_SECONDS = max(120, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800")))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set BOT_TOKEN or TELEGRAM_BOT_TOKEN in the container environment")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("tiktokreeloraa")

dp = Dispatcher()
sem = asyncio.Semaphore(MAX_CONCURRENT)
pending_urls: dict[str, str] = {}
pending_uploads: dict[str, tuple[str, str]] = {}

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)

PLATFORMS = {
    "tiktok.com": "TikTok", "instagram.com": "Instagram", "youtube.com": "YouTube",
    "youtu.be": "YouTube", "x.com": "X", "twitter.com": "X", "facebook.com": "Facebook",
    "fb.watch": "Facebook", "reddit.com": "Reddit", "redd.it": "Reddit",
    "pinterest.com": "Pinterest", "pin.it": "Pinterest", "vk.com": "VK",
}


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS downloads (cache_key TEXT PRIMARY KEY, path TEXT, title TEXT, size INTEGER, created INTEGER)")
    con.commit()
    return con


def normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/?")


def clean_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,)]}>\"'")


def platform(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    for domain, name in PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "Other"


def fmt_bytes(n: int | None) -> str:
    if not n:
        return "—"
    units = ["B", "KB", "MB", "GB"]
    value = float(n)
    for u in units:
        if value < 1024 or u == units[-1]:
            return f"{value:.1f} {u}"
        value /= 1024
    return "—"


def quality_text(info: dict) -> str:
    w, h, fps = info.get("width"), info.get("height"), info.get("fps")
    bits = info.get("tbr")
    parts = []
    if w and h: parts.append(f"{w}×{h}")
    if fps: parts.append(f"{fps:.0f} FPS")
    if bits: parts.append(f"{bits:.0f} kbps")
    return " • ".join(parts) or "максимально доступное"


def cleanup_old_jobs() -> None:
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    for p in DOWNLOAD_DIR.iterdir():
        try:
            if p.name != "cache" and p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def cached(cache_key: str):
    con = db()
    row = con.execute("SELECT path,title,size,created FROM downloads WHERE cache_key=?", (cache_key,)).fetchone()
    con.close()
    if row and Path(row[0]).exists():
        return {"path": row[0], "title": row[1], "size": row[2], "created": row[3]}
    return None


def save_cache(cache_key: str, path: Path, title: str):
    cache_dir = DOWNLOAD_DIR / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{hashlib.sha256(cache_key.encode()).hexdigest()[:20]}{path.suffix.lower()}"
    shutil.copy2(path, cache_path)
    con = db()
    con.execute("INSERT OR REPLACE INTO downloads VALUES (?,?,?,?,?)", (cache_key, str(cache_path), title, cache_path.stat().st_size, int(time.time())))
    con.commit(); con.close()


def download(url: str, job: Path, hook):
    output = str(job / "%(title).100B.%(ext)s")
    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 1,
        "fragment_retries": 1,
        "concurrent_fragment_downloads": 8,
        "socket_timeout": 30,
        "continuedl": False,
        "overwrites": False,
        "progress_hooks": [hook],
        "postprocessors": [],
        "windowsfilenames": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    media = [p for p in job.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}]
    if not media:
        raise RuntimeError("Загрузчик не создал видеофайл.")
    path = max(media, key=lambda p: p.stat().st_size)
    return path, info


def resize_video(source: Path, output: Path, mode: str) -> Path:
    sizes = {"shorts": (1080, 1920), "video": (1920, 1080)}
    width, height = sizes[mode]
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(source), "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(output),
    ], check=True, capture_output=True, text=True)
    return output


def keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Скачать максимум", callback_data="quality:best")],
        [InlineKeyboardButton(text="ℹ️ О качестве", callback_data="quality:info")],
    ])


def format_keyboard(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Shorts → Видео", callback_data=f"format:shorts:video:{key}"), InlineKeyboardButton(text="📱 Shorts → Файл", callback_data=f"format:shorts:document:{key}")],
        [InlineKeyboardButton(text="🖥️ 16:9 → Видео", callback_data=f"format:video:video:{key}"), InlineKeyboardButton(text="🖥️ 16:9 → Файл", callback_data=f"format:video:document:{key}")],
        [InlineKeyboardButton(text="🎞️ Оригинал → Видео", callback_data=f"format:original:video:{key}"), InlineKeyboardButton(text="🎞️ Оригинал → Файл", callback_data=f"format:original:document:{key}")],
    ])


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎬 <b>Media Downloader</b>\n\n"
        "Отправь публичную ссылку на видео. Я выберу максимально доступное качество, "
        "после этого предложу формат: YouTube Shorts 9:16, обычное видео 16:9 или оригинал.\n\n"
        "Поддерживаются многие источники через yt-dlp: TikTok, Instagram, YouTube, X, "
        "Facebook, Reddit, Pinterest, VK и другие.\n\n"
        "⚠️ Если watermark уже встроен в исходный файл, скачивание его не удаляет.",
        parse_mode="HTML",
        reply_markup=keyboard(),
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "<b>Как использовать</b>\n\n"
        "1. Скопируй ссылку на публичное видео.\n"
        "2. Отправь её сюда и выбери формат результата.\n"
        "3. Бот скачает лучший доступный поток и подготовит файл.\n\n"
        "Shorts: 1080×1920 с кадрированием по центру.\n"
        "Обычное видео: 1920×1080 с кадрированием по центру.\n"
        "Оригинал отправляется без повторного видеокодирования.\n\n"
        "Приватные материалы и обход авторизации не поддерживаются.", parse_mode="HTML"
    )


@dp.callback_query(F.data == "quality:info")
async def quality_info(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "<b>Что значит MAX QUALITY?</b>\n\n"
        "• выбирается лучший доступный видеопоток;\n"
        "• отдельно выбирается лучший аудиопоток, если источник их разделяет;\n"
        "• FFmpeg используется только для merge/remux;\n"
        "• видео не уменьшается до 640px и не пережимается;\n"
        "• бот не добавляет watermark.\n\n"
        "Если исходник содержит watermark, простой downloader не может сделать его невидимым без обработки видео.",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "quality:best")
async def quality_best(call: CallbackQuery):
    await call.answer("Просто отправь ссылку на видео")


@dp.callback_query(F.data.startswith("format:"))
async def format_choice(call: CallbackQuery):
    await call.answer()
    _, mode, delivery, key = call.data.split(":", 3)
    url = pending_urls.pop(key, None)
    upload = pending_uploads.pop(key, None)
    if not call.message:
        return
    if not url and not upload:
        await call.message.answer("Эта ссылка устарела. Отправь её ещё раз.")
        return
    if url:
        await process_url(call.message, url, mode, delivery)
    else:
        await process_upload(call.message, upload[0], upload[1], mode, delivery)


@dp.message(F.text)
async def url_handler(message: Message):
    url = clean_url(message.text or "")
    if not url:
        await message.answer("Отправь ссылку на видео, например https://www.tiktok.com/...")
        return

    key = uuid.uuid4().hex[:12]
    pending_urls[key] = url
    await message.answer(
        "Выбери формат и способ отправки:\n\n"
        "Видео — Telegram покажет плеер.\n"
        "Файл — отправка без обработки Telegram.\n"
        "Shorts и 16:9 меняют только кадрирование, оригинал сохраняется без перекодирования.",
        reply_markup=format_keyboard(key),
    )


@dp.message(F.video)
async def video_handler(message: Message):
    if not message.video:
        return
    key = uuid.uuid4().hex[:12]
    pending_uploads[key] = (message.video.file_id, message.video.file_name or "uploaded_video.mp4")
    await message.answer(
        "Видео получено. Выбери формат и способ отправки результата:",
        reply_markup=format_keyboard(key),
    )


@dp.message(F.document)
async def document_video_handler(message: Message):
    document = message.document
    if not document or not (document.mime_type or "").startswith("video/"):
        return
    key = uuid.uuid4().hex[:12]
    pending_uploads[key] = (document.file_id, document.file_name or "uploaded_video.mp4")
    await message.answer(
        "Видео-файл получен. Выбери формат и способ отправки результата:",
        reply_markup=format_keyboard(key),
    )


async def send_result(message: Message, path: Path, caption: str, delivery: str):
    if delivery == "video":
        await message.answer_video(FSInputFile(path), caption=caption, parse_mode="HTML", supports_streaming=True)
    else:
        await message.answer_document(FSInputFile(path), caption=caption, parse_mode="HTML")


async def process_upload(message: Message, file_id: str, title: str, mode: str, delivery: str):
    job = DOWNLOAD_DIR / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=True)
    status = await message.answer("📥 Получаю видео…")
    try:
        source = job / Path(title).name
        await message.bot.download(
            file_id,
            destination=source,
            timeout=REQUEST_TIMEOUT_SECONDS,
            chunk_size=1024 * 1024,
        )
        result_path = source if mode == "original" else resize_video(source, job / f"{source.stem}_{mode}.mp4", mode)
        size = result_path.stat().st_size
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            await status.edit_text(f"⚠️ Файл готов: {fmt_bytes(size)}, но превышает лимит {MAX_UPLOAD_MB} MB.")
            return
        label = {"shorts": "YouTube Shorts 9:16", "video": "Видео 16:9", "original": "Оригинал"}[mode]
        delivery_label = "Видео" if delivery == "video" else "Файл"
        await status.edit_text("📤 Отправляю…")
        await send_result(message, result_path, f"✅ <b>Готово</b>\n🎬 {title}\n📐 {label}\n📨 {delivery_label}\n📦 {fmt_bytes(size)}", delivery)
        try: await status.delete()
        except Exception: pass
    except Exception as exc:
        log.exception("Upload processing error")
        await status.edit_text("❌ Не удалось обработать видео\n\n" + str(exc)[:900])
    finally:
        shutil.rmtree(job, ignore_errors=True)


async def process_url(message: Message, url: str, mode: str, delivery: str):

    cleanup_old_jobs()
    cache_key = normalize_url(url)
    cached_item = cached(cache_key)
    if mode == "original" and cached_item and Path(cached_item["path"]).stat().st_size <= MAX_UPLOAD_MB * 1024 * 1024:
        await send_result(message, Path(cached_item["path"]), f"⚡ <b>Уже скачано</b>\n🎬 {cached_item['title']}\n📦 {fmt_bytes(cached_item['size'])}", delivery)
        return

    p = platform(url)
    status = await message.answer(f"🔎 <b>{p}</b>\nПроверяю доступное качество…", parse_mode="HTML")
    job = DOWNLOAD_DIR / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=True)
    state = {"last": 0.0, "text": ""}

    def hook(d):
        if d.get("status") != "downloading": return
        now = time.monotonic()
        if now - state["last"] < 2: return
        state["last"] = now
        pct = d.get("_percent_str", "?").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        state["text"] = f"⬇️ {pct}" + (f" • {speed}" if speed else "") + (f" • ETA {eta}" if eta else "")
        async def update():
            try: await status.edit_text(state["text"])
            except Exception: pass
        try: asyncio.get_running_loop().create_task(update())
        except RuntimeError: pass

    try:
        async with sem:
            if cached_item:
                path = Path(cached_item["path"])
                info = {"title": cached_item["title"]}
                await status.edit_text("⚡ Использую сохранённое видео…")
            else:
                await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
                path, info = await asyncio.to_thread(download, url, job, hook)
                save_cache(cache_key, path, info.get("title") or path.stem)

        result_path = path
        if mode != "original":
            result_path = resize_video(path, job / f"{path.stem}_{mode}.mp4", mode)

        size = result_path.stat().st_size
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            await status.edit_text(
                f"⚠️ Файл готов: {fmt_bytes(size)}.\n\n"
                f"Я не буду сжимать его ради отправки, потому что это ухудшит качество.\n"
                f"Лимит текущей конфигурации: {MAX_UPLOAD_MB} MB."
            )
            return

        title = info.get("title") or path.stem
        q = quality_text(info)
        await status.edit_text(f"📤 Отправляю…\n🎬 {title}\n📐 {q}\n📦 {fmt_bytes(size)}")
        label = {"shorts": "YouTube Shorts 9:16", "video": "Видео 16:9", "original": "Оригинал"}[mode]
        note = "с перекодированием под выбранный формат" if mode != "original" else "без повторного видеокодирования"
        delivery_label = "Видео" if delivery == "video" else "Файл"
        await send_result(message, result_path, (f"✅ <b>Готово</b>\n🎬 {title}\n📐 {label}\n📨 {delivery_label}\n📦 {fmt_bytes(size)}\nℹ️ {note}")[:1024], delivery)
        try: await status.delete()
        except Exception: pass
    except Exception as exc:
        log.exception("Download error")
        msg = str(exc).replace("\n", " ")
        if len(msg) > 900: msg = msg[-900:]
        await status.edit_text("❌ <b>Не удалось скачать</b>\n\n" + msg, parse_mode="HTML")
    finally:
        shutil.rmtree(job, ignore_errors=True)


async def main():
    bot = Bot(TOKEN, session=AiohttpSession(timeout=REQUEST_TIMEOUT_SECONDS))
    log.info("Starting Telegram bot")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
