Development (dengan hot-reload):
```
podman-compose up -d --build
```

Production:
```
podman-compose -f podman-compose.prod.yml up -d --build
```

Perbedaan Development vs Production:
Development:

Volume mount source code untuk hot-reload
--reload flag untuk auto-restart
npm run dev untuk Next.js HMR
Tidak ada restart policy
Production:

Tidak mount source code (menggunakan built image)
Optimized build dengan multi-stage
npm start untuk Next.js production server
restart: unless-stopped untuk auto-restart jika crash
Minified dan optimized assets
