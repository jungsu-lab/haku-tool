from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


NARRATIVE_STAGES = {"hook", "setup", "buildup", "climax", "resolution", "cta"}
PURPOSES = {"attention", "explanation", "emotion", "product_emphasis", "transition", "cta"}
AUDIO_STATUSES = {"deferred_by_user", "deferred_by_rights", "reviewed", "not_present"}
AUDIO_POLICIES = {"deferred_by_user", "deferred_by_rights", "reference_audio_reviewed", "licensed_library_track"}
CONFIDENCE = {"low", "medium", "high"}
SECTIONS = {
    "narrative": {"stage", "function"},
    "shot": {"shot_type", "subject", "framing", "camera_angle", "camera_motion", "shot_duration_seconds"},
    "cut": {"cut_type", "cut_reason", "incoming_motion", "outgoing_motion", "continuity"},
    "timing": {"pace", "rhythm", "beat_position", "pause_seconds", "speed_change"},
    "transition": {"transition_type", "duration_seconds", "direction", "visual_anchor", "sound_anchor"},
    "text": {"content", "font_style", "position", "emphasis", "animation", "duration_seconds"},
    "color": {"exposure", "contrast", "saturation", "temperature", "palette", "mood"},
    "audio": {"status", "dialogue", "music", "sfx", "ambience", "beat", "volume_curve"},
    "motion": {"zoom", "pan", "shake", "tracking", "easing", "motion_blur"},
    "purpose": {"primary", "effect_name", "when_used", "applied_scene", "why_used", "viewer_feeling"},
}


def nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(payload: dict) -> list[str]:
    errors: list[str] = []
    strict_v11 = payload.get("schema_version") == "1.1"
    duration_field = "timeline_duration_seconds" if strict_v11 else "source_duration_seconds"
    duration = payload.get(duration_field)
    if not isinstance(duration, (int, float)) or duration <= 0:
        errors.append(f"{duration_field} must be greater than zero")
        duration = 0
    audio_policy = payload.get("audio_policy")
    if audio_policy not in AUDIO_POLICIES:
        errors.append("audio_policy must be deferred_by_user, deferred_by_rights, reference_audio_reviewed, or licensed_library_track")
    timeline_fps = payload.get("timeline_fps") if strict_v11 else None
    if strict_v11:
        if not isinstance(timeline_fps, (int, float)) or timeline_fps <= 0:
            errors.append("timeline_fps must be greater than zero for schema 1.1")
        if payload.get("artifact_type") not in {"reference_analysis", "proof_edit", "final_edit"}:
            errors.append("artifact_type is invalid for schema 1.1")
        toolchain = payload.get("toolchain")
        if not isinstance(toolchain, dict):
            errors.append("toolchain must be an object for schema 1.1")
        else:
            for field in ("primary_editor", "secondary_tools", "why_this_toolchain"):
                if field not in toolchain:
                    errors.append(f"toolchain missing: {field}")
            if not nonempty_text(toolchain.get("primary_editor")):
                errors.append("toolchain.primary_editor must be non-empty")
            if not isinstance(toolchain.get("secondary_tools"), list):
                errors.append("toolchain.secondary_tools must be a list")
            if not nonempty_text(toolchain.get("why_this_toolchain")):
                errors.append("toolchain.why_this_toolchain must be non-empty")
        if audio_policy == "licensed_library_track":
            for field in ("audio_rights_manifest", "music_event_map"):
                if not nonempty_text(payload.get(field)):
                    errors.append(f"{field} is required for licensed_library_track")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        return errors + ["events must be a non-empty list"]
    seen: set[str] = set()
    previous_start = -1.0
    for index, event in enumerate(events):
        prefix = f"events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be an object")
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(f"{prefix}.event_id must be non-empty")
        elif event_id in seen:
            errors.append(f"{prefix}.event_id is duplicated")
        else:
            seen.add(event_id)
        start, end = event.get("start_seconds"), event.get("end_seconds")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            errors.append(f"{prefix} requires numeric start_seconds and end_seconds")
        else:
            if start < 0 or end <= start or end > duration + 1e-6:
                errors.append(f"{prefix} has an invalid timeline range")
            if start < previous_start:
                errors.append(f"{prefix} is not ordered by start_seconds")
            previous_start = start
        for field in ("observation", "inference"):
            if not isinstance(event.get(field), str) or not event[field].strip():
                errors.append(f"{prefix}.{field} must be non-empty")
        for section, required in SECTIONS.items():
            value = event.get(section)
            if not isinstance(value, dict):
                errors.append(f"{prefix}.{section} must be an object")
                continue
            missing = sorted(required - set(value))
            if missing:
                errors.append(f"{prefix}.{section} missing: {', '.join(missing)}")
        if event.get("narrative", {}).get("stage") not in NARRATIVE_STAGES:
            errors.append(f"{prefix}.narrative.stage is invalid")
        if strict_v11:
            mapping = event.get("source_mapping")
            if not isinstance(mapping, dict):
                errors.append(f"{prefix}.source_mapping must be an object")
            else:
                for field in ("source_clip_id", "source_path", "source_sha256"):
                    if not nonempty_text(mapping.get(field)):
                        errors.append(f"{prefix}.source_mapping.{field} must be non-empty")
                if nonempty_text(mapping.get("source_sha256")) and not re.fullmatch(
                    r"[0-9A-Fa-f]{64}", str(mapping["source_sha256"])
                ):
                    errors.append(f"{prefix}.source_mapping.source_sha256 must be SHA-256")
                source_fps = mapping.get("source_fps")
                if not isinstance(source_fps, (int, float)) or source_fps <= 0:
                    errors.append(f"{prefix}.source_mapping.source_fps must be positive")
                numeric_fields = (
                    "source_in_seconds", "source_out_seconds", "source_frame_in",
                    "source_frame_out_exclusive", "output_in_seconds", "output_out_seconds",
                    "output_frame_in", "output_frame_out_exclusive",
                )
                for field in numeric_fields:
                    if not isinstance(mapping.get(field), (int, float)):
                        errors.append(f"{prefix}.source_mapping.{field} must be numeric")
                if mapping.get("retime") != "none":
                    errors.append(f"{prefix}.source_mapping.retime must be none")
                numeric_fields_valid = all(
                    isinstance(mapping.get(field), (int, float)) for field in numeric_fields
                ) and isinstance(source_fps, (int, float)) and source_fps > 0 and isinstance(timeline_fps, (int, float)) and timeline_fps > 0
                if numeric_fields_valid and isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    tolerance = 1.0 / float(timeline_fps) + 1e-6
                    if abs(float(mapping["output_in_seconds"]) - float(start)) > 1e-6 or abs(float(mapping["output_out_seconds"]) - float(end)) > 1e-6:
                        errors.append(f"{prefix}.source_mapping output seconds must match event range")
                    expected_output_in = round(float(start) * float(timeline_fps))
                    expected_output_out = round(float(end) * float(timeline_fps))
                    if int(mapping["output_frame_in"]) != expected_output_in or int(mapping["output_frame_out_exclusive"]) != expected_output_out:
                        errors.append(f"{prefix}.source_mapping output frames must match timeline_fps")
                    if float(mapping["source_in_seconds"]) < 0 or float(mapping["source_out_seconds"]) <= float(mapping["source_in_seconds"]):
                        errors.append(f"{prefix}.source_mapping source range is invalid")
                    if abs(
                        (float(mapping["source_out_seconds"]) - float(mapping["source_in_seconds"]))
                        - (float(end) - float(start))
                    ) > tolerance:
                        errors.append(f"{prefix}.source_mapping source duration must match output duration without retime")
                    expected_source_frame_in = math.ceil(float(mapping["source_in_seconds"]) * float(source_fps) - 1e-9)
                    if int(mapping["source_frame_in"]) != expected_source_frame_in:
                        errors.append(f"{prefix}.source_mapping source_frame_in does not match source time")
                    expected_source_frame_out = math.ceil(
                        float(mapping["source_out_seconds"]) * float(source_fps) - 1e-9
                    )
                    if int(mapping["source_frame_out_exclusive"]) != expected_source_frame_out:
                        errors.append(f"{prefix}.source_mapping source_frame_out_exclusive does not match source time")
            narrative = event.get("narrative", {})
            if not nonempty_text(narrative.get("function")):
                errors.append(f"{prefix}.narrative.function must be non-empty")
            shot = event.get("shot", {})
            for field in ("shot_type", "subject", "framing", "camera_angle", "camera_motion"):
                if not nonempty_text(shot.get(field)):
                    errors.append(f"{prefix}.shot.{field} must be non-empty")
            shot_duration = shot.get("shot_duration_seconds")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                if not isinstance(shot_duration, (int, float)) or abs(float(shot_duration) - float(end - start)) > 0.001:
                    errors.append(f"{prefix}.shot.shot_duration_seconds must match the event range")
            cut = event.get("cut", {})
            for field in ("cut_type", "cut_reason", "incoming_motion", "outgoing_motion", "continuity"):
                if not nonempty_text(cut.get(field)):
                    errors.append(f"{prefix}.cut.{field} must be non-empty")
            timing = event.get("timing", {})
            for field in ("pace", "rhythm", "beat_position", "speed_change"):
                if not nonempty_text(timing.get(field)):
                    errors.append(f"{prefix}.timing.{field} must be non-empty")
            if not isinstance(timing.get("pause_seconds"), (int, float)) or timing.get("pause_seconds", -1) < 0:
                errors.append(f"{prefix}.timing.pause_seconds must be zero or greater")
            transition = event.get("transition", {})
            for field in ("transition_type", "direction", "visual_anchor", "sound_anchor"):
                if not nonempty_text(transition.get(field)):
                    errors.append(f"{prefix}.transition.{field} must be non-empty")
            if not isinstance(transition.get("duration_seconds"), (int, float)) or transition.get("duration_seconds", -1) < 0:
                errors.append(f"{prefix}.transition.duration_seconds must be zero or greater")
            text_layer = event.get("text", {})
            if text_layer.get("content") == "":
                for field in ("font_style", "position", "emphasis", "animation"):
                    if text_layer.get(field) != "none":
                        errors.append(f"{prefix}.text.{field} must be none when content is empty")
                if text_layer.get("duration_seconds") != 0.0:
                    errors.append(f"{prefix}.text.duration_seconds must be 0 when content is empty")
            elif not nonempty_text(text_layer.get("content")):
                errors.append(f"{prefix}.text.content must be text")
            color = event.get("color", {})
            for field in ("exposure", "contrast", "saturation", "temperature", "mood"):
                if not nonempty_text(color.get(field)):
                    errors.append(f"{prefix}.color.{field} must be non-empty")
            if not isinstance(color.get("palette"), list) or not color.get("palette"):
                errors.append(f"{prefix}.color.palette must contain at least one color")
            motion = event.get("motion", {})
            for field in ("zoom", "pan", "shake", "tracking", "easing", "motion_blur"):
                if not nonempty_text(motion.get(field)):
                    errors.append(f"{prefix}.motion.{field} must be non-empty")
        purpose = event.get("purpose", {})
        if purpose.get("primary") not in PURPOSES:
            errors.append(f"{prefix}.purpose.primary is invalid")
        for field in ("effect_name", "when_used", "applied_scene", "why_used"):
            if not isinstance(purpose.get(field), str) or not purpose[field].strip():
                errors.append(f"{prefix}.purpose.{field} must be non-empty")
        feelings = purpose.get("viewer_feeling")
        if not isinstance(feelings, list) or not feelings or not all(isinstance(x, str) and x.strip() for x in feelings):
            errors.append(f"{prefix}.purpose.viewer_feeling must contain text")
        audio = event.get("audio", {})
        if audio.get("status") not in AUDIO_STATUSES:
            errors.append(f"{prefix}.audio.status is invalid")
        if audio_policy in {"deferred_by_user", "deferred_by_rights"}:
            if audio.get("status") != audio_policy:
                errors.append(f"{prefix}.audio.status must preserve {audio_policy}")
            for field in ("dialogue", "music", "sfx", "ambience", "beat", "volume_curve"):
                if audio.get(field) != "not_reviewed":
                    errors.append(f"{prefix}.audio.{field} must be not_reviewed while audio is deferred")
        elif strict_v11:
            if audio.get("status") != "reviewed":
                errors.append(f"{prefix}.audio.status must be reviewed when audio is in scope")
            for field in ("music", "beat", "volume_curve"):
                if not nonempty_text(audio.get(field)) or audio.get(field) == "not_reviewed":
                    errors.append(f"{prefix}.audio.{field} must be reviewed when audio is in scope")
            if event.get("timing", {}).get("beat_position") == "not_reviewed":
                errors.append(f"{prefix}.timing.beat_position must be reviewed when audio is in scope")
            if event.get("transition", {}).get("sound_anchor") == "not_reviewed":
                errors.append(f"{prefix}.transition.sound_anchor must be reviewed when audio is in scope")
        if event.get("confidence") not in CONFIDENCE:
            errors.append(f"{prefix}.confidence is invalid")
    if strict_v11:
        narrative_arc = payload.get("narrative_arc")
        if not isinstance(narrative_arc, dict):
            errors.append("narrative_arc must be an object for schema 1.1")
        else:
            for stage in sorted(NARRATIVE_STAGES):
                entry = narrative_arc.get(stage)
                if not isinstance(entry, dict):
                    errors.append(f"narrative_arc.{stage} must be an object")
                    continue
                status = entry.get("status")
                event_ids = entry.get("event_ids")
                reason = entry.get("reason")
                if status not in {"present", "not_applicable"}:
                    errors.append(f"narrative_arc.{stage}.status is invalid")
                if not isinstance(event_ids, list):
                    errors.append(f"narrative_arc.{stage}.event_ids must be a list")
                elif status == "present":
                    if not event_ids or any(event_id not in seen for event_id in event_ids):
                        errors.append(f"narrative_arc.{stage}.event_ids must reference existing events")
                elif event_ids:
                    errors.append(f"narrative_arc.{stage}.event_ids must be empty when not_applicable")
                if not nonempty_text(reason):
                    errors.append(f"narrative_arc.{stage}.reason must be non-empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    errors = validate(payload)
    print(json.dumps({"valid": not errors, "event_count": len(payload.get("events", [])), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
