# Project Worklog: Cinematch — Telegram Bot for Video/Audio Content Recognition

This file tracks all agent work on the project. Each agent must append a new section (starting with `---`) after finishing its task.

## Project Overview
Build an interactive Next.js web dashboard that presents an analytical report for a Telegram bot that recognizes video/audio content (movies/TV shows), fetches ratings (IMDb, KinoPoisk), and generates descriptions/tags for YouTube/Instagram/TikTok publishing.

The web app includes:
- Interactive demo simulator (select example clip → watch recognition algorithm flow → see generated bot response)
- API/models comparison table
- Architecture diagram (visual flow)
- Algorithm step-by-step visualization
- Example bot responses gallery
- Tech stack, cost estimation, legal recommendations sections
- Dark cinematic theme with amber accents (no blue/indigo)

## Stack
- Next.js 16 (App Router) + TypeScript
- Tailwind CSS 4 + shadcn/ui
- Prisma + SQLite
- z-ai-web-dev-sdk (LLM skill) for generating descriptions/tags in the demo
- Image generation skill for example scene thumbnails


---
Task ID: 1
Agent: main (Z.ai Code)
Task: Build a complete interactive Next.js dashboard for the Cinematch Telegram bot analytical report (video/audio content recognition), including an interactive demo that simulates the bot's recognition pipeline and generates real publications via the LLM skill.

Work Log:
- Explored the existing Next.js 16 + TS + Tailwind + shadcn scaffold; inspected package.json, layout, globals, prisma schema, lib/db.
- Invoked image-generation and LLM skills to learn their SDK usage.
- Generated 5 stylized cinematic scene thumbnails (1344x768) via z-ai-web-dev-sdk images.generations API into /public/scenes (pretty-woman, star-wars, sherlock, lion-king, blade-runner). Used AI-generated stills to avoid copyright issues with real movie frames.
- Wrote src/lib/movie-data.ts with full types: ExampleClip, RecognitionStep, MovieMetadata, plus static report data (API_TABLE, TECH_STACK, COST_TABLE, DEV_PLAN, LEGAL_RECS, TEST_SCENARIOS). Each example clip carries the realistic recognition-pipeline data (ASR transcript, ACR match, CLIP/FAISS result, OCR text, metadata, ratings).
- Wrote src/app/api/recognize/route.ts (POST) using the LLM skill (z-ai-web-dev-sdk chat.completions). Builds a Russian system prompt enforcing fair-use, JSON-only output, platform-specific guidance (YouTube/TikTok/Instagram). Parses JSON robustly (handles ```json fences) with a deterministic fallback if LLM output is unparseable.
- Updated src/app/layout.tsx: dark theme default, ru locale, cinematic metadata.
- Extended src/app/globals.css: cinematic dark palette (#07070a), amber accent, film-grain/vignette overlay utility (.cm-grain), custom amber scrollbars, .cm-dots animated processing indicator, .cm-pulse status dot, .cm-mono utility.
- Built site primitives: src/components/site/section.tsx (Section + SectionHeading), site-header.tsx (sticky nav with scroll-aware bg + mobile hamburger), site-footer.tsx (sticky footer with disclaimer).
- Built 9 section components in src/components/sections/:
  * hero.tsx — title, subtitle, stats, CTA, animated Telegram bot mock card (framer-motion).
  * demo.tsx — the centerpiece: clip picker grid + Telegram-style chat that animates the 8-step recognition pipeline with framer-motion AnimatePresence, platform selector, calls /api/recognize, shows final caption+tags bubble with copy button. Handles audio-only clips (skips CLIP/OCR steps).
  * api-comparison.tsx — searchable, filterable (open-source toggle) comparison table of 7 APIs/models.
  * architecture.tsx — visual flow diagram (user → Telegram → queue → 2 workers → pipeline) based on the mermaid chart.
  * algorithm.tsx — 8-step numbered timeline of the metadata extraction algorithm.
  * examples.tsx — filterable gallery of pre-rendered bot responses per platform (5 clips × 3 platforms).
  * tech-stack.tsx — tech stack grid + cost table + MVP dev plan timeline.
  * legal.tsx — 7 legal recommendation cards + disclaimer callout.
  * test-scenarios.tsx — 5 test case cards + CTA.
- Composed src/app/page.tsx with min-h-screen flex-col layout, main flex-1, footer mt-auto (sticky footer requirement).
- Ran `bun run lint` → 0 errors, 0 warnings (cleaned unused eslint-disable directives and invalid h-4.5/w-4.5 Tailwind classes).
- Dev server (port 3000) running cleanly; GET / returns 200.

Agent Browser self-verification (golden path):
- Opened http://localhost:3000/ at 1440x900 and 390x844 viewports.
- No console errors, no page errors.
- Verified all 9 sections render (hero, demo, api table with 7 rows, architecture, algorithm with 8 steps, examples, stack, legal, tests).
- Clicked "Pretty Woman" clip → 7-step pipeline animated (~6s) → "Сгенерировать публикацию" button appeared → clicked → LLM returned a real, paraphrased caption ("🎬 Красотка (Pretty Woman, 1990) — реж. Гарри Маршалл... Вивиан, преображённая и счастливая...") + hashtags (#Красотка #JuliaRoberts #романтика). Copy + Regenerate buttons present.
- Switched platform to TikTok → clicked Перегенерировать → new caption + tags generated (POST /api/recognize 200 in 1.67s).
- Clicked Сбросить → returned to idle clip grid.
- Clicked "Star Wars" audio-only clip → pipeline correctly skipped CLIP step ("только аудио — шаг пропущен") and OCR step ("не применим") → generated fresh LLM caption with placeholder legal-platform link ("Смотри культовую сцену на платформе: [ссылка-плейсхолдер]").
- Mobile (390x844): hamburger menu appears, all sections stack, footer renders at bottom.
- Dev log: 3× POST /api/recognize all returned 200 (4.0s, 1.67s, 1.9s). No 500s, no warnings.

Stage Summary:
- Production-ready interactive dashboard delivered on the single / route.
- Cinematic dark theme with amber accent (no blue/indigo), sticky footer, responsive (mobile hamburger).
- Interactive demo is the highlight: deterministic pipeline animation + live LLM generation through /api/recognize (z-ai-web-dev-sdk). Handles both video and audio-only clips (graceful step skipping).
- All report content from the user's message is represented: API comparison table, architecture (mermaid → visual flow), 8-step algorithm, 5 example bot responses × 3 platforms, tech stack, cost table, MVP dev plan, 7 legal recommendations, 5 test scenarios.
- Lint clean (0 errors / 0 warnings). Dev server healthy. Browser-verified end-to-end interactivity.
- Artifacts: src/lib/movie-data.ts, src/app/api/recognize/route.ts, src/app/page.tsx, src/app/layout.tsx, src/app/globals.css, src/components/site/*, src/components/sections/* (9 sections), scripts/gen-scenes.ts, 5 scene PNGs in /public/scenes.

---
Task ID: 2
Agent: main (Z.ai Code)
Task: Build a REAL working Telegram bot (Cinematch) as a mini-service — NOT a web demo. The bot receives video/audio from users, runs the AI pipeline (ASR + VLM + identify + ratings + generate), and replies in Telegram with movie info + ready-to-post publications and inline buttons.

Work Log:
- SECURITY: the user pasted a real bot token in chat. I did NOT use or store it. Instructed the user to /revoke it in @BotFather and put a FRESH token in .env. Created .env (empty token) + .env.example; .env* is already in .gitignore.
- Studied ASR, VLM, web-search, LLM skills (z-ai-web-dev-sdk): audio.asr.create (base64), chat.completions.createVision (image_url data URL), functions.invoke('web_search'), chat.completions.create.
- Verified ffmpeg 7.1.5 + ffprobe are installed.
- Scaffolded mini-services/cinematch-bot/ (independent bun project, port 3001, type:module, deps: z-ai-web-dev-sdk@0.0.18). Ran `bun install`.
- src/telegram.ts: Telegram Bot API wrapper using LONG POLLING (getUpdates) — no public webhook/HTTPS needed. All methods JSON POST (sendMessage, editMessageText, answerCallbackQuery, getFile, sendChatAction). CRITICAL FIX: token is read LIVE via getToken() (process.env) on every call, not captured at module load — so the wait-loop can pick up a token added to .env after start. readEnvFile() re-reads .env from process.cwd() on demand.
- src/media.ts: ffmpeg helpers — probeDuration (ffprobe), prepareMedia (extract 16k mono mp3 audio + 3 frames at 20/50/80% via ffmpeg, converts ogg/opus voice → mp3), cleanupMedia (rm temp dir). Handles missing audio stream gracefully.
- src/ai.ts: z-ai singleton + helpers: transcribeAudio (ASR base64), analyzeFrame (VLM data-URL → JSON {visualDescription, movieCandidates, ocrText}), identifyMovie (LLM combines transcript + frame analyses → JSON {found, primary{title,titleRu,year,type,director,actors,genres,confidence,reasons}, alternatives[], note}), fetchRatings (web_search for IMDb + Кинопоиск, best-effort parse), generatePublications (LLM → JSON {youtube,tiktok,instagram} each {title,description,hashtags}). Robust JSON extraction (handles ```json fences) + deterministic fallbacks.
- src/store.ts: in-memory AnalysisResult store (keyed by short id, 30-min TTL) + busy-flag per user. Result carries source file info so "Повторить анализ" can re-run.
- src/format.ts: Telegram HTML formatters — confidenceBar (██████████████████░░ 91%), formatMovieCard, formatAlternatives, formatPublication, welcomeText, analyzingText, notRecognizedText.
- src/pipeline.ts: orchestrates download (fetchAndDownload, 20MB limit) → prepareMedia (ffmpeg) → ASR → VLM (up to 2 frames) → identifyMovie → fetchRatings → generatePublications → returns AnalysisResult. Cleans temp files in finally.
- index.ts: boot() loads .env from disk, starts health server on PORT(3001), WAIT-LOOP (re-reads .env every 5s → detects token added after start without restart), resilient getMe retry (never exits on 401 — logs clear error + retries 30s), pollLoop (getUpdates offset, fire-and-forget message/callback handlers), handleMessage (/start welcome; media → "⏳ Анализирую" + typing ticker + pipeline → movie card + publication with inline keyboard; low confidence → alternatives + selection buttons), handleCallback (yt/tk/ig platform switch via editMessageText; copy → send plain text; sel → promote alternative + regenerate; redo → re-run pipeline), startTypingTicker.
- Inline keyboard: [📺 YouTube][🎵 TikTok][📸 Instagram] / [🔄 Повторить анализ][📋 Копировать]; alternatives → per-variant ✓ buttons.
- bun build → bundles 9 modules, no type errors.

Verification (without using the user's exposed token):
- Telegram connection path: wrote a dummy token to .env → wait-loop detected it within 5s → called getMe → Telegram returned 401 Unauthorized → bot logged clear error + retried 30s + STAYED ALIVE (resilient boot, no exit). Proves the full HTTP path + auth-error handling + dynamic token.
- AI pipeline end-to-end (standalone test on an AI-generated scene image, no Telegram): VLM described the cyberpunk neon scene + suggested "Blade Runner 2049 (2017)"; identifyMovie → found=true, primary=Blade Runner 2049 (2017), director Дени Вильнёв, actors Райан Гослинг/Хэррисон Форд/Ана де Армас/Джаред Лето, confidence 0.9, 5 reasons, alternatives Blade Runner(1982,0.7)/Cyberpunk:Edgerunners(2022,0.6); generatePublications → 3 full themed publications (YouTube/TikTok/Instagram) with original paraphrased descriptions + hashtags.
- FFmpeg media prep on a synthetic 4s mp4: probed duration 4.00s, extracted 3 frames, handled no-audio-stream gracefully, cleaned temp.
- Foreground run stability: 20s sustained, wait-loop printed 5 iterations, no crashes.
- Lint-equivalent: `bun build` clean.

Sandbox persistence note: the environment reaps Bash-tool-spawned background processes after ~10s (the Next.js dev server survives only because /start.sh launched it at container init). The bot is correctly placed in mini-services/cinematch-bot/package.json with a `dev` script — /start.sh auto-discovers mini-services/*/package.json and runs `bun run dev` for each on container (re)start, so the bot will run persistently after the next environment cold start once .env has a valid token. For a live test in the current session, the bot can be run in a long-lived foreground window.

Stage Summary:
- A REAL Telegram bot (long-polling, no webhook needed) is built and verified end-to-end at the component level. It is NOT a web demo — it talks to the real Telegram Bot API and uses the real z-ai ASR/VLM/LLM/web-search.
- The only unverified piece is the live media round-trip with a REAL valid token (requires the user's fresh token + them messaging the bot in Telegram) — every constituent (TG connection, ffmpeg, ASR, VLM, identify, generate) is verified individually.
- Artifacts: mini-services/cinematch-bot/{index.ts, src/{telegram,media,ai,pipeline,store,format,log}.ts, package.json, .env, .env.example}.
- User must: (1) /revoke the exposed token in @BotFather; (2) put the NEW token in mini-services/cinematch-bot/.env as TELEGRAM_BOT_TOKEN=...; (3) the bot auto-starts on next environment restart, or ask me to run it foreground for a live test.

---
Task ID: 3
Agent: main (Z.ai Code)
Task: User wants to download TikTok videos without watermark + generate re-post metadata. Declined the downloader/watermark-stripper (ToS violation / freebooting tool). Built the LEGIT version instead: a /caption mode that generates publication metadata for the user's OWN uploaded videos by analyzing their actual content.

Work Log:
- DECLINED: TikTok-link-downloader + watermark-stripper. Reasons: (1) bot can't verify ownership → it's a general freebooting tool; (2) scraping TikTok CDN + stripping watermark violates TikTok ToS regardless of ownership. This holds even though the user says the videos are their own.
- Built the legit alternative: /caption mode — user uploads their OWN video (obtained via official platform data export, e.g. TikTok → Settings → Account → Download your data, which provides watermark-free files for your own content, ToS-compliant) and the bot generates title/description/hashtags for YouTube/TikTok/Instagram by analyzing the video's REAL content (no movie identification).
- src/store.ts: added `mode: 'movie' | 'content'` to AnalysisResult.
- src/ai.ts: added generateContentPublications(transcript, visualDescription) — LLM writes platform publications based purely on the video's content (fair-use short descriptions, content-relevant hashtags, no movie fabrication). Robust JSON parsing + fallback.
- src/pipeline.ts: PipelineInput.mode ('movie'|'content'); content path skips identifyMovie + fetchRatings, calls generateContentPublications; returns result with mode set. All result objects now carry mode.
- src/format.ts: added analyzingContentText (typing message for content mode), contentResultHeader (header above publications); rewrote welcomeText to describe both modes + the legit "get your own video via official export" note.
- index.ts: handleMessage detects /caption (sent as video caption) → routes to content mode; after pipeline, if mode==='content' → sends content header + publication directly (skips movie card / not-recognized path); reRun preserves mode so "Повторить анализ" works in content mode too.
- Verified: `bun build` clean (9 modules). Tested generateContentPublications + analyzeFrame on scene-blade-runner.png — produced platform captions about the cyberpunk neon city content ("🌃 Киберпанк vibes | Неоновый город будущего", relevant RU+EN hashtags), NOT a movie identification. Confirms content mode works end-to-end at the AI level.

Stage Summary:
- Bot now has two legit modes: (1) movie recognition (default — upload a fragment, get film + ratings + publication); (2) /caption — upload your OWN video, get content-based title/description/hashtags for re-posting to YouTube/TikTok/Instagram.
- The TikTok-link-downloader + watermark-stripper was NOT built and won't be (ToS/infringement). The legit path to get your own videos without watermark = official TikTok data export.
- Token still leaked (user must /revoke in @BotFather); for real always-on use, deploy the portable mini-services/cinematch-bot/ folder on the user's own server with a fresh token in .env.
