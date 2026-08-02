from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from validate_audio_rights import validate as validate_audio_rights
from validate_music_event_map import validate as validate_music_event_map


DEFERRED_POLICIES = {"deferred_by_user", "deferred_by_rights"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def resolve(recipe_path: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (recipe_path.parent / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def prepare_licensed_audio(
    recipe_path: Path,
    recipe: dict[str, Any],
    timeline_duration_seconds: float,
) -> dict[str, Any] | None:
    policy = recipe.get("audio_policy")
    if policy in DEFERRED_POLICIES:
        return None
    if policy != "licensed_library_track":
        raise ValueError("audio_policy must be deferred_by_user, deferred_by_rights, or licensed_library_track")
    block = recipe.get("licensed_audio")
    if not isinstance(block, dict):
        raise ValueError("licensed_audio must be an object")
    if block.get("same_for_plain_and_proof") is not True:
        raise ValueError("licensed_audio.same_for_plain_and_proof must be true")
    audio_file = resolve(recipe_path, str(block.get("file", "")))
    rights_file = resolve(recipe_path, str(block.get("audio_rights_manifest", "")))
    event_map_file = resolve(recipe_path, str(block.get("music_event_map", "")))
    timeline_file = resolve(recipe_path, str(block.get("timeline_grammar", "")))

    rights = json.loads(rights_file.read_text(encoding="utf-8"))
    rights_for_validation = dict(rights)
    source_file = Path(str(rights.get("source_file", "")))
    if not source_file.is_absolute():
        source_file = (rights_file.parent / source_file).resolve()
    rights_for_validation["source_file"] = str(source_file)
    rights_errors = validate_audio_rights(rights_for_validation, check_file=True)
    if rights_errors:
        raise ValueError("audio rights validation failed: " + "; ".join(rights_errors))
    if source_file != audio_file:
        raise ValueError("licensed_audio.file must be the same file recorded in audio-rights.json")

    timeline = json.loads(timeline_file.read_text(encoding="utf-8"))
    visual_event_ids = {
        event.get("event_id")
        for event in timeline.get("events", [])
        if isinstance(event, dict)
    }
    if timeline.get("audio_policy") != "licensed_library_track":
        raise ValueError("timeline grammar must use licensed_library_track")
    event_map = json.loads(event_map_file.read_text(encoding="utf-8"))
    map_errors = validate_music_event_map(event_map, visual_event_ids)
    if map_errors:
        raise ValueError("music event map validation failed: " + "; ".join(map_errors))
    linked_rights = resolve(event_map_file, str(event_map.get("audio_rights_manifest", "")))
    if linked_rights != rights_file:
        raise ValueError("music-event-map must link the selected audio-rights.json")

    file_hash = sha256(audio_file)
    if file_hash.lower() != str(rights.get("sha256", "")).lower():
        raise ValueError("audio file hash does not match audio-rights.json")
    if file_hash.lower() != str(event_map.get("audio_file_sha256", "")).lower():
        raise ValueError("audio file hash does not match music-event-map.json")

    source_in = float(block.get("source_in_seconds", -1))
    source_out = float(block.get("source_out_seconds", -1))
    if source_in < 0 or source_out <= source_in:
        raise ValueError("licensed audio source range is invalid")
    if abs(source_in - float(event_map.get("track_source_in_seconds", -1))) > 0.001:
        raise ValueError("licensed audio source_in must match music-event-map")
    if abs(source_out - float(event_map.get("track_source_out_seconds", -1))) > 0.001:
        raise ValueError("licensed audio source_out must match music-event-map")
    if source_out - source_in + 0.001 < timeline_duration_seconds:
        raise ValueError("licensed audio source range is shorter than the visual timeline")

    gain_db = float(block.get("gain_db", -12.0))
    fade_in = float(block.get("fade_in_seconds", 0.0))
    fade_out = float(block.get("fade_out_seconds", 0.0))
    if not -60.0 <= gain_db <= 6.0:
        raise ValueError("licensed_audio.gain_db must be within -60..6")
    if fade_in < 0 or fade_out < 0 or fade_in + fade_out > timeline_duration_seconds:
        raise ValueError("licensed audio fades are invalid for the timeline duration")

    return {
        "file": audio_file,
        "sha256": file_hash,
        "rights_manifest": rights_file,
        "music_event_map": event_map_file,
        "timeline_grammar": timeline_file,
        "source_in_seconds": source_in,
        "source_out_seconds": source_out,
        "gain_db": gain_db,
        "fade_in_seconds": fade_in,
        "fade_out_seconds": fade_out,
        "duration_seconds": timeline_duration_seconds,
        "same_for_plain_and_proof": True,
    }


def mux_licensed_audio(
    ffmpeg: Path,
    video: Path,
    audio: dict[str, Any],
    run: Callable[..., Any],
    max_threads: int,
) -> None:
    duration = float(audio["duration_seconds"])
    source_in = float(audio["source_in_seconds"])
    source_end = source_in + duration
    gain_db = float(audio["gain_db"])
    fade_in = float(audio["fade_in_seconds"])
    fade_out = float(audio["fade_out_seconds"])
    filters = [
        f"atrim=start={source_in:.6f}:end={source_end:.6f}",
        "asetpts=PTS-STARTPTS",
        f"volume={gain_db:.3f}dB",
    ]
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in:.6f}")
    if fade_out > 0:
        filters.append(f"afade=t=out:st={max(0.0, duration - fade_out):.6f}:d={fade_out:.6f}")
    filters.extend([f"atrim=duration={duration:.6f}", "asetpts=PTS-STARTPTS[aout]"])
    temporary = video.with_name(video.stem + ".licensed-audio-tmp" + video.suffix)
    command = [
        str(ffmpeg), "-hide_banner", "-nostdin", "-y",
        "-i", str(video), "-i", str(audio["file"]),
        "-filter_complex", ",".join(filters),
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-threads", str(max_threads), "-movflags", "+faststart",
        "-t", f"{duration:.6f}", str(temporary),
    ]
    run(command)
    os.replace(temporary, video)


def report_audio(audio: dict[str, Any] | None, policy: str) -> dict[str, Any]:
    if audio is None:
        return {"policy": policy, "stream_expected": False}
    return {
        "policy": "licensed_library_track",
        "stream_expected": True,
        "file": str(audio["file"]),
        "sha256": audio["sha256"],
        "rights_manifest": str(audio["rights_manifest"]),
        "music_event_map": str(audio["music_event_map"]),
        "timeline_grammar": str(audio["timeline_grammar"]),
        "source_range_seconds": [audio["source_in_seconds"], audio["source_out_seconds"]],
        "gain_db": audio["gain_db"],
        "fade_in_seconds": audio["fade_in_seconds"],
        "fade_out_seconds": audio["fade_out_seconds"],
        "same_for_plain_and_proof": True,
    }
