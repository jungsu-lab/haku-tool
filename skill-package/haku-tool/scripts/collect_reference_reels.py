#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_ENDPOINT = "https://igfetcher.com/api/profile"
CONTENT_ENDPOINT = "https://igfetcher.com/api/content"
ALLOWED_USERNAME = "haku_.photo"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
)


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "x-igfetcher-client": "web",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def repair_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    broken_markers = ("Ã", "â", "ã", "å", "æ", "é")
    return repaired if sum(text.count(marker) for marker in broken_markers) else text


def content_query(profile: dict[str, Any], cursor: str | None = None) -> str:
    params = {
        "amount": "18",
        "type": "reels",
        "user_id": str(profile["id"]),
        "username": str(profile["username"]),
        "full_name": str(profile.get("fullName") or ""),
        "biography": str(profile.get("biography") or ""),
        "avatar_url": str(profile.get("avatarUrl") or ""),
        "followers": str(profile.get("followers") or 0),
        "following": str(profile.get("following") or 0),
        "media_count": str(profile.get("mediaCount") or 0),
    }
    if cursor:
        params["cursor"] = cursor
    return f"{CONTENT_ENDPOINT}?{urllib.parse.urlencode(params)}"


def enumerate_reels(
    profile: dict[str, Any],
    required_new_count: int,
    excluded_codes: set[str],
    max_pages: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen = set(excluded_codes)
    cursor: str | None = None
    for page_index in range(max_pages):
        payload = request_json(content_query(profile, cursor))
        for item in payload.get("items", []):
            code = str(item.get("code") or "")
            if (
                not code
                or code in seen
                or item.get("type") != "video"
                or item.get("source") != "reels"
            ):
                continue
            seen.add(code)
            selected.append(item)
            if len(selected) >= required_new_count:
                return selected
        cursor = payload.get("nextCursor")
        if not cursor:
            break
        print(
            f"Enumerated page {page_index + 1}: "
            f"{len(selected)}/{required_new_count} new Reels"
        )
        time.sleep(1.0)
    raise RuntimeError(
        f"Only {len(selected)} distinct public Reels were found; "
        f"{required_new_count} were requested."
    )


def download_file(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
            "Referer": "https://www.instagram.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        with temporary.open("wb") as handle:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                handle.write(block)
    if temporary.stat().st_size < 10_000:
        raise RuntimeError(f"Downloaded file is unexpectedly small: {temporary}")
    temporary.replace(destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_media(path: Path, ffprobe: Path | None) -> dict[str, Any]:
    if ffprobe is None:
        return {}
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffprobe rejected {path.name}: {completed.stderr.strip()}"
        )
    result = json.loads(completed.stdout)
    streams = result.get("streams", [])
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise RuntimeError(f"No video stream found: {path}")
    return result


def date_token(taken_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        return parsed.strftime("%Y%m%d")
    except ValueError:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect distinct public haku_.photo Reels one item at a time for "
            "local reference analysis."
        )
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--existing-manifest", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--start-index", type=int, default=11)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--ffprobe")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()

    if args.count < 1 or args.count > 60:
        parser.error("--count must be from 1 to 60")
    output_dir = Path(args.output_dir).expanduser().resolve()
    existing_manifest_path = Path(args.existing_manifest).expanduser().resolve()
    output_manifest_path = Path(args.output_manifest).expanduser().resolve()
    ffprobe = (
        Path(args.ffprobe).expanduser().resolve() if args.ffprobe else None
    )
    if not existing_manifest_path.is_file():
        parser.error(f"existing manifest not found: {existing_manifest_path}")
    if ffprobe is not None and not ffprobe.is_file():
        parser.error(f"ffprobe not found: {ffprobe}")

    existing_manifest = json.loads(
        existing_manifest_path.read_text(encoding="utf-8-sig")
    )
    existing_items = list(existing_manifest.get("items", []))
    excluded_codes = {
        str(item.get("post_id") or item.get("code") or "")
        for item in existing_items
    }
    excluded_codes.discard("")

    profile = request_json(
        f"{PROFILE_ENDPOINT}?{urllib.parse.urlencode({'username': ALLOWED_USERNAME})}"
    )
    if profile.get("username") != ALLOWED_USERNAME:
        raise RuntimeError("Profile identity did not match haku_.photo")
    if bool(profile.get("isPrivate")):
        raise RuntimeError("The profile is private; collection is not allowed.")

    candidates = enumerate_reels(
        profile,
        required_new_count=args.count,
        excluded_codes=excluded_codes,
        max_pages=args.max_pages,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    new_items: list[dict[str, Any]] = []

    for offset, item in enumerate(candidates):
        index = args.start_index + offset
        code = str(item["code"])
        taken_at = str(item.get("takenAt") or "")
        filename = f"{index:02d}_{date_token(taken_at)}_{code}.mp4"
        destination = output_dir / filename
        if not destination.is_file():
            print(f"Downloading {offset + 1}/{len(candidates)}: {code}")
            media_url = str(item.get("downloadUrl") or item.get("url") or "")
            if not media_url:
                raise RuntimeError(f"No public media URL returned for {code}")
            download_file(media_url, destination)
            time.sleep(max(0.0, args.sleep_seconds))
        technical = inspect_media(destination, ffprobe)
        new_items.append(
            {
                "index": index,
                "filename": filename,
                "creator": ALLOWED_USERNAME,
                "post_id": code,
                "original_url": str(
                    item.get("originalUrl")
                    or f"https://www.instagram.com/reel/{code}/"
                ),
                "taken_at": taken_at,
                "caption": repair_text(item.get("caption")),
                "duration_reported": item.get("duration"),
                "like_count": item.get("likeCount"),
                "comment_count": item.get("commentCount"),
                "play_count": item.get("playCount"),
                "rights": "public-reference-only",
                "reuse_in_final": False,
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "retrieval": (
                    "Public Reel enumerated via IG Fetcher public endpoint and "
                    "downloaded individually from the returned public CDN URL; "
                    "no login or cookies"
                ),
                "technical": technical,
            }
        )

    combined = sorted(
        [*existing_items, *new_items],
        key=lambda entry: int(entry.get("index") or 0),
    )
    manifest = {
        "schema_version": "2.0",
        "source_profile": "https://www.instagram.com/haku_.photo/reels/",
        "creator": ALLOWED_USERNAME,
        "profile_private_at_collection": False,
        "rights": "public-reference-only",
        "reuse_in_final": False,
        "collection_method": (
            "Profile used only to enumerate public Reel URLs; each selected Reel "
            "was retrieved and recorded as an individual post."
        ),
        "count": len(combined),
        "existing_count": len(existing_items),
        "new_count": len(new_items),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "items": combined,
    }
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = output_manifest_path.with_suffix(
        output_manifest_path.suffix + ".partial"
    )
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_manifest.replace(output_manifest_path)
    print(
        json.dumps(
            {
                "success": True,
                "new_count": len(new_items),
                "total_count": len(combined),
                "manifest": str(output_manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
