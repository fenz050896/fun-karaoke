# YouTube Authentication Issue

## Problem
YouTube sekarang memerlukan autentikasi untuk mencegah bot detection. Semua search request akan gagal dengan error:
```
Sign in to confirm you're not a bot
```

## Solution: Export Cookies dari Browser

### Langkah 1: Install Browser Extension
Install salah satu extension berikut untuk export cookies:
- Chrome/Edge: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

### Langkah 2: Login ke YouTube
1. Buka https://youtube.com di browser
2. Login dengan akun Google Anda
3. Pastikan Anda sudah login

### Langkah 3: Export Cookies
1. Klik extension yang sudah diinstall
2. Export cookies untuk youtube.com
3. Save file sebagai `youtube_cookies.txt`

### Langkah 4: Simpan Cookies di Backend
```bash
mkdir -p backend/youtube-auth
cp youtube_cookies.txt backend/youtube-auth/youtube_cookies.txt.tmp
mv backend/youtube-auth/youtube_cookies.txt.tmp backend/youtube-auth/youtube_cookies.txt
```

Simpan melalui file sementara lalu `mv` agar backend tidak membaca file saat export/copy belum selesai.

Compose memasang direktori khusus `backend/youtube-auth/` ke container supaya file hasil export yang mengganti inode tetap terbaca. Setelah menarik perubahan mount ini untuk pertama kali, recreate backend:

```bash
podman-compose up -d --force-recreate backend
```

Export cookie berikutnya tidak memerlukan restart jika diperbarui melalui file sementara lalu `mv` seperti di atas.

> Pada konfigurasi lama, `podman-compose restart` dapat mempertahankan single-file bind mount ke inode lama sehingga backend masih membaca cookie yang sudah usang.

### Langkah 5: Update Code (sudah dilakukan)
Code sudah diupdate untuk menggunakan cookies jika tersedia.

## Alternative: Gunakan Video ID Langsung
Jika Anda sudah tahu video ID dari YouTube, Anda bisa langsung memasukkan URL atau video ID tanpa perlu search.

## References
- https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
- https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies
