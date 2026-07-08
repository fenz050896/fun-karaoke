# Deploy Next.js Standalone + Nginx

## Context

User ingin production deployment. Next.js `output: 'standalone'` — build jadi folder mandiri berisi `server.js` + semua dependency di-bundle. Nginx di depan untuk SSL, static caching, dan proxy `/api/` ke backend.

## Current Project Status

**Last checked:** 2026-07-08

**Implemented in repo:**
- `frontend/next.config.ts` has `output: 'standalone'`.
- `frontend/package.json` has `"start": "node server.js"`.
- `frontend/Dockerfile` builds and copies `.next/standalone`, `.next/static`, and `public`.
- `podman-compose.prod.yml` runs frontend with `node server.js`.
- `nginx/karaoke.defigroup.id.conf` exists and proxies `/api/` to backend and `/` to Next.js.

**Verified now:**
- `cd frontend && npm run build` passes.

**Still not verified now:**
- `.next/standalone/server.js` runtime smoke with `node`.
- Nginx syntax/reload on target server.
- Live domain check.
- Dynamic karaoke route and YouTube/search/queue/play live flow.
- Static asset cache header check.

## Approach

`output: 'standalone'` di `next.config.ts`. Build produksi `server.js` yang jalan di Node.js. Nginx reverse proxy dengan optimasi cache untuk static assets (`/_next/static`).

## Files to Modify

### 1. `frontend/next.config.ts`
- Tambah `output: 'standalone'`

### 2. `frontend/Dockerfile`
Rewrite untuk standalone mode:
- Build stage: `npm ci && npm run build`
- Output stage: copy `.next/standalone` + `.next/static` + `public`
- CMD: `node server.js`
- Tidak perlu `npm ci --only=production` (semua sudah di-bundle di standalone)

### 3. Nginx config (`/etc/nginx/sites-enabled/df-karaoke`)
Perubahan:
- `/_next/static` → alias ke folder static dengan cache 1 tahun (immutable assets)
- `/_next/image` → proxy ke Next.js (image optimization, jika dipakai)
- `/api/` → tetap proxy ke backend `localhost:8000`
- `/` → tetap proxy ke Next.js `localhost:3000`

### 4. `podman-compose.prod.yml`
- Update frontend service: port mapping, env, command

### 5. `frontend/package.json`
- Tambah script `"start": "node server.js"` (untuk standalone, bukan `next start`)

## Verification

1. `cd frontend && npm run build` — cek output ada `.next/standalone/server.js`
2. `node .next/standalone/server.js` — test jalan manual, buka `http://localhost:3000`
3. Nginx reload: `nginx -t && nginx -s reload`
4. Buka `https://df-karaoke.duckdns.org` — app jalan normal
5. Navigasi ke `/karaoke/VIDEO_ID` — route dynamic jalan
6. Search YouTube, add to queue, play — semua fitur normal
7. Cek `/_next/static/*` — response ada cache header
