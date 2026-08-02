from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EVENT_TYPES = {"phrase_start", "beat", "accent", "break", "drop", "instrument_change", "ending"}
VISUAL_RESPONSES = {"cut", "hold", "in_frame_event", "panel_change", "text_change", "color_change", "none"}
CONFIDENCE = {"low", "medium", "high"}
ANALYSIS_METHODS = {"waveform", "onset_detection", "direct_listening"}


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(payload: dict, timeline_event_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if not text(payload.get("audio_rights_manifest")):
        errors.append("audio_rights_manifest must be non-empty")
    sha256 = str(payload.get("audio_file_sha256", ""))
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", sha256):
        errors.append("audio_file_sha256 must contain 64 hexadecimal characters")
    source_in = payload.get("track_source_in_seconds")
    source_out = payload.get("track_source_out_seconds")
    if not isinstance(source_in, (int, float)) or source_in < 0:
        errors.append("track_source_in_seconds must be zero or greater")
    if not isinstance(source_out, (int, float)) or source_out <= 0:
        errors.append("track_source_out_seconds must be greater than zero")
    if isinstance(source_in, (int, float)) and isinstance(source_out, (int, float)) and source_out <= source_in:
        errors.append("track_source_out_seconds must be after track_source_in_seconds")
    methods = payload.get("analysis_method")
    if not isinstance(methods, list) or "direct_listening" not in methods:
        errors.append("analysis_method must include direct_listening")
    elif any(method not in ANALYSIS_METHODS for method in methods):
        errors.append("analysis_method contains an invalid value")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        return errors + ["events must be a non-empty list"]
    seen: set[str] = set()
    previous_timeline = -1.0
    linked_visual_events = 0
    for index, event in enumerate(events):
        prefix = f"events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be an object")
            continue
        event_id = event.get("event_id")
        if not text(event_id):
            errors.append(f"{prefix}.event_id must be non-empty")
        elif event_id in seen:
            errors.append(f"{prefix}.event_id must be unique")
        else:
            seen.add(event_id)
        track_seconds = event.get("track_seconds")
        timeline_seconds = event.get("timeline_seconds")
        if not isinstance(track_seconds, (int, float)) or track_seconds < 0:
            errors.append(f"{prefix}.track_seconds must be zero or greater")
        if not isinstance(timeline_seconds, (int, float)) or timeline_seconds < 0:
            errors.append(f"{prefix}.timeline_seconds must be zero or greater")
        elif timeline_seconds < previous_timeline:
            errors.append(f"{prefix}.timeline_seconds must be chronological")
        else:
            previous_timeline = timeline_seconds
        if event.get("type") not in EVENT_TYPES:
            errors.append(f"{prefix}.type is invalid")
        if not text(event.get("observation")):
            errors.append(f"{prefix}.observation must be non-empty")
        response = event.get("visual_response")
        if response not in VISUAL_RESPONSES:
            errors.append(f"{prefix}.visual_response is invalid")
        target = event.get("target_visual_event_id")
        if response == "none":
            if text(target):
                errors.append(f"{prefix}.target_visual_event_id must be empty when visual_response is none")
        else:
            if not text(target):
                errors.append(f"{prefix}.target_visual_event_id is required for an active visual response")
            else:
                linked_visual_events += 1
                if timeline_event_ids is not None and target not in timeline_event_ids:
                    errors.append(f"{prefix}.target_visual_event_id does not exist in timeline grammar")
        offset = event.get("intentional_offset_ms")
        if not isinstance(offset, (int, float)) or abs(offset) > 1000:
            errors.append(f"{prefix}.intentional_offset_ms must be within -1000..1000")
        if event.get("confidence") not in CONFIDENCE:
            errors.append(f"{prefix}.confidence is invalid")
    if linked_visual_events == 0:
        errors.append("at least one music event must intentionally change a visual event")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_map", type=Path)
    parser.add_argument("--timeline-grammar", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.event_map.read_text(encoding="utf-8"))
    timeline_event_ids = None
    if args.timeline_grammar:
        timeline = json.loads(args.timeline_grammar.read_text(encoding="utf-8"))
        timeline_event_ids = {event.get("event_id") for event in timeline.get("events", []) if isinstance(event, dict)}
    errors = validate(payload, timeline_event_ids=timeline_event_ids)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
