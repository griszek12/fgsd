"""
YoutubeViewer313 Proxy Server
Compatible with com.cheongyang.youtubeviewer (iOS 3.1.3 app)

API endpoints:
  GET /api/video?id=<videoId>
  GET /api/trending
  GET /api/search?q=<query>
  GET /api/stream?id=<videoId>[&quality=<quality>]
  GET /api/thumbnail?id=<videoId>
  GET /api/quality-info?id=<videoId>&duration=<duration>
"""

import os
import json
import logging
import requests
from flask import Flask, request, jsonify, redirect, abort
import yt_dlp

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))

# ─── helpers ────────────────────────────────────────────────────────────────

YDL_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
}

def _ydl_info(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(YDL_BASE_OPTS) as ydl:
        return ydl.extract_info(url, download=False)

def _format_video(info: dict) -> dict:
    """Trim yt-dlp info to what the iOS 3.x app needs."""
    return {
        "id":          info.get("id", ""),
        "title":       info.get("title", ""),
        "description": (info.get("description") or "")[:200],
        "duration":    info.get("duration", 0),
        "view_count":  info.get("view_count", 0),
        "uploader":    info.get("uploader", ""),
        "thumbnail":   f"/api/thumbnail?id={info.get('id', '')}",
    }

def _best_stream_url(info: dict, quality: str | None = None) -> str | None:
    """
    Pick the best (or quality-matched) direct stream URL.
    iOS 3.x can only play H.264 + AAC inside MP4/MOV – so we avoid webm/opus.
    """
    formats = info.get("formats", [])

    # Build candidate list: mp4 with video+audio merged (or audio-only fallback)
    candidates = [
        f for f in formats
        if f.get("ext") in ("mp4", "m4a", "mov")
        and f.get("vcodec", "none") != "none"
        and f.get("acodec", "none") != "none"
        and f.get("url")
    ]

    if not candidates:
        # Fallback: any mp4 with video
        candidates = [
            f for f in formats
            if f.get("ext") in ("mp4", "m4a", "mov")
            and f.get("url")
        ]

    if not candidates:
        return None

    # Sort by height (resolution) ascending
    candidates.sort(key=lambda f: f.get("height") or 0)

    if quality:
        q = quality.lower()
        if q in ("360", "360p", "medium"):
            target = 360
        elif q in ("240", "240p", "low"):
            target = 240
        elif q in ("144", "144p", "lowest"):
            target = 144
        elif q in ("480", "480p"):
            target = 480
        elif q in ("720", "720p", "hd"):
            target = 720
        else:
            target = None

        if target:
            match = next(
                (f for f in candidates if (f.get("height") or 0) <= target),
                None,
            )
            if match:
                return match["url"]

    # Default: lowest quality that still has video (best for old devices)
    return candidates[0]["url"]

def _available_qualities(info: dict) -> list[dict]:
    formats = info.get("formats", [])
    seen = set()
    result = []
    for f in formats:
        h = f.get("height")
        if not h or f.get("ext") not in ("mp4", "m4a", "mov"):
            continue
        label = f"{h}p"
        if label not in seen:
            seen.add(label)
            result.append({"label": label, "height": h})
    result.sort(key=lambda x: x["height"])
    return result

def _search_videos(query: str, max_results: int = 20) -> list[dict]:
    opts = {
        **YDL_BASE_OPTS,
        "extract_flat": True,
        "playlistend": max_results,
    }
    url = f"ytsearch{max_results}:{query}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(url, download=False)
    entries = result.get("entries", []) if result else []
    return [
        {
            "id":       e.get("id", ""),
            "title":    e.get("title", ""),
            "duration": e.get("duration", 0),
            "uploader": e.get("uploader") or e.get("channel", ""),
            "thumbnail": f"/api/thumbnail?id={e.get('id', '')}",
        }
        for e in entries
        if e and e.get("id")
    ]

def _trending_videos(max_results: int = 20) -> list[dict]:
    opts = {
        **YDL_BASE_OPTS,
        "extract_flat": True,
        "playlistend": max_results,
    }
    # YouTube trending playlist (US)
    url = "https://www.youtube.com/feed/trending"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(url, download=False)
        entries = result.get("entries", []) if result else []
        return [
            {
                "id":       e.get("id", ""),
                "title":    e.get("title", ""),
                "duration": e.get("duration", 0),
                "uploader": e.get("uploader") or e.get("channel", ""),
                "thumbnail": f"/api/thumbnail?id={e.get('id', '')}",
            }
            for e in entries
            if e and e.get("id")
        ][:max_results]
    except Exception as exc:
        logger.warning("Trending fetch failed, falling back to search: %s", exc)
        return _search_videos("trending music 2024", max_results)


# ─── routes ─────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return jsonify({"status": "YoutubeViewer313 proxy running", "version": "1.5"})


@app.get("/api/video")
def api_video():
    video_id = request.args.get("id", "").strip()
    if not video_id:
        return jsonify({"error": "missing id"}), 400
    try:
        info = _ydl_info(video_id)
        return jsonify(_format_video(info))
    except Exception as exc:
        logger.error("video error %s: %s", video_id, exc)
        return jsonify({"error": str(exc)}), 500


@app.get("/api/trending")
def api_trending():
    try:
        videos = _trending_videos()
        return jsonify({"videos": videos})
    except Exception as exc:
        logger.error("trending error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.get("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "missing q"}), 400
    try:
        videos = _search_videos(query)
        return jsonify({"videos": videos})
    except Exception as exc:
        logger.error("search error '%s': %s", query, exc)
        return jsonify({"error": str(exc)}), 500


@app.get("/api/stream")
def api_stream():
    video_id = request.args.get("id", "").strip()
    quality  = request.args.get("quality", "").strip() or None
    if not video_id:
        return jsonify({"error": "missing id"}), 400
    try:
        info = _ydl_info(video_id)
        stream_url = _best_stream_url(info, quality)
        if not stream_url:
            return jsonify({"error": "no suitable stream found"}), 404
        # iOS 3.x MPMoviePlayerController follows redirects fine
        return redirect(stream_url, code=302)
    except Exception as exc:
        logger.error("stream error %s: %s", video_id, exc)
        return jsonify({"error": str(exc)}), 500


@app.get("/api/thumbnail")
def api_thumbnail():
    video_id = request.args.get("id", "").strip()
    if not video_id:
        abort(400)
    # Redirect to YouTube's own CDN thumbnail – no yt-dlp call needed
    thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    return redirect(thumb_url, code=302)


@app.get("/api/quality-info")
def api_quality_info():
    video_id = request.args.get("id", "").strip()
    if not video_id:
        return jsonify({"error": "missing id"}), 400
    try:
        info = _ydl_info(video_id)
        qualities = _available_qualities(info)
        return jsonify({"id": video_id, "qualities": qualities})
    except Exception as exc:
        logger.error("quality-info error %s: %s", video_id, exc)
        return jsonify({"error": str(exc)}), 500


# ─── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
