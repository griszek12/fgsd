# YoutubeViewer313 – Proxy Server

Serwer proxy kompatybilny z apką **YoutubeViewer** (`com.cheongyang.youtubeviewer`)
dla iOS 3.1.3 (jailbreak / Cydia).

---

## Endpointy API

| Endpoint | Opis |
|---|---|
| `GET /api/video?id=<ID>` | Info o filmie |
| `GET /api/trending` | Trendy (top 20) |
| `GET /api/search?q=<query>` | Wyszukiwarka |
| `GET /api/stream?id=<ID>[&quality=360p]` | Redirect do streamu MP4 |
| `GET /api/thumbnail?id=<ID>` | Miniaturka (redirect do YT CDN) |
| `GET /api/quality-info?id=<ID>&duration=<sek>` | Dostępne jakości |

Dostępne wartości `quality`: `144p`, `240p`, `360p`, `480p`, `720p`

---

## Wdrożenie na Render (darmowe)

### 1. Wrzuć na GitHub
```bash
git init
git add .
git commit -m "init yt313 proxy"
git remote add origin https://github.com/TWOJ_NICK/yt313-server.git
git push -u origin main
```

### 2. Utwórz serwis na Render
1. Wejdź na [render.com](https://render.com) → **New → Web Service**
2. Połącz swoje repo GitHub
3. Render automatycznie wykryje `render.yaml`
4. Kliknij **Deploy**
5. Za kilka minut dostaniesz URL, np.:  
   `https://yt313-proxy.onrender.com`

### 3. Skonfiguruj apkę na iPhone
W ustawieniach apki YoutubeViewer wpisz:
- **Host**: `yt313-proxy.onrender.com`
- **Port**: `443` (HTTPS) lub `80`

> ⚠️ **Uwaga:** Free tier na Render usypia po 15 min bezczynności.
> Pierwsze żądanie po uśpieniu może trwać ~30 sek.
> Aby temu zapobiec, zmień `plan: free` na `plan: starter` w `render.yaml`.

---

## Lokalne testowanie

```bash
pip install -r requirements.txt
python app.py
# serwer startuje na http://localhost:8080
```

Testuj w przeglądarce:
```
http://localhost:8080/api/trending
http://localhost:8080/api/search?q=chill+music
http://localhost:8080/api/video?id=dQw4w9WgXcQ
http://localhost:8080/api/stream?id=dQw4w9WgXcQ&quality=360p
```

---

## Jak to działa

```
iPhone (iOS 3.1.3)
   │  HTTP  (http://host:port)
   ▼
Render (ten serwer – Python/Flask)
   │  yt-dlp
   ▼
YouTube → zwraca redirect do MP4
```

`yt-dlp` wyciąga bezpośredni URL do pliku MP4 (H.264 + AAC),
który iOS 3.x potrafi odtworzyć przez `MPMoviePlayerController`.
