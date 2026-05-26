# Fun Karaoke

On-demand karaoke from YouTube with AI stem separation and synced lyrics.

## Features

- YouTube search + audio download via yt-dlp
- Stem separation (vocals/instrumental) with Demucs
- Synced lyrics via Whisper transcription
- Instant karaoke/full mode switching (Web Audio API)
- Play queue with drag-to-reorder
- Mobile-friendly responsive layout

## Prerequisites

- **Podman** (or Docker)
- **YouTube cookies** — required for search and download (see below)

## YouTube Cookies (crucial)

YouTube blocks bot requests. You must export browser cookies:

1. Install [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) (Chrome) or [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) (Firefox)
2. Login to https://youtube.com in your browser
3. Click the extension → export cookies for `youtube.com`
4. Save the file as `backend/youtube_cookies.txt`

```
cp youtube_cookies.txt backend/
```

Without this file, YouTube search and download **will fail**.

## Quick Start

### Development (hot-reload)

```bash
podman-compose up -d --build
```

- Frontend: `npm run dev` with HMR (port 3000)
- Backend: `uvicorn --reload` (port 8000)
- Source code volume-mounted for live editing

### Production

```bash
podman-compose -f podman-compose.prod.yml up -d --build
```

- Frontend: `output: 'standalone'` Next.js server
- Backend: optimized Python image
- `restart: unless-stopped`

Access at `http://localhost:3000` (or behind nginx at your domain).

## Architecture

```
Browser → Nginx → /api/* → Backend (FastAPI, port 8000)
                 → /*     → Frontend (Next.js standalone, port 3000)

Backend:
  youtube.py     — yt-dlp search + download (YouTube cookies required)
  stems.py       — Demucs stem separation (vocals, bass, drums, other)
  lyrics_sync.py — Whisper transcription + lyric fetching
  main.py        — FastAPI server, job queue, audio serving

Frontend:
  audio-context.tsx  — Web Audio API player (dual AudioBuffer, gain toggle)
  karaoke/[videoId]/ — Karaoke playback page with synced lyrics
  components/        — MiniPlayer, search interface
```

## Ports

| Service  | Dev  | Prod |
|----------|------|------|
| Frontend | 3000 | 3000 |
| Backend  | 8000 | 8000 |

## Data

All downloaded audio and processed stems are stored in `data/downloads/` and `data/processed/` (gitignored). Processed tracks persist across restarts.
