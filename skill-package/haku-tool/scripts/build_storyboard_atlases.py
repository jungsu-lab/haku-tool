#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine per-Reel storyboards into review atlases."
    )
    parser.add_argument("--corpus-metrics", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--per-page", type=int, default=5)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--end-index", type=int)
    args = parser.parse_args()

    corpus_path = Path(args.corpus_metrics).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    reels = [
        reel
        for reel in corpus["reels"]
        if int(reel["index"]) >= args.start_index
        and (args.end_index is None or int(reel["index"]) <= args.end_index)
    ]
    if not reels:
        raise RuntimeError("No Reels matched the requested index range.")
    output_dir.mkdir(parents=True, exist_ok=True)
    page_count = int(math.ceil(len(reels) / args.per_page))
    outputs: list[str] = []

    for page in range(page_count):
        selected = reels[page * args.per_page : (page + 1) * args.per_page]
        sections: list[np.ndarray] = []
        for reel in selected:
            storyboard_path = Path(reel["storyboard"])
            storyboard = cv2.imdecode(
                np.fromfile(str(storyboard_path), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if storyboard is None:
                raise RuntimeError(f"Unable to read {reel['storyboard']}")
            scale = args.width / storyboard.shape[1]
            resized = cv2.resize(
                storyboard,
                (args.width, int(round(storyboard.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
            header = np.full((74, args.width, 3), 245, dtype=np.uint8)
            title = (
                f"{int(reel['index']):02d}  {reel['reel_id']}  "
                f"{float(reel['duration']):.1f}s  "
                f"{int(reel['shot_count'])} shots"
            )
            cv2.putText(
                header,
                title,
                (18, 46),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.82,
                (18, 18, 18),
                2,
                cv2.LINE_AA,
            )
            sections.extend(
                [
                    header,
                    resized,
                    np.full((18, args.width, 3), 225, dtype=np.uint8),
                ]
            )
        atlas = np.vstack(sections)
        first_index = int(selected[0]["index"])
        last_index = int(selected[-1]["index"])
        output_path = output_dir / (
            f"atlas-{first_index:02d}-{last_index:02d}.jpg"
        )
        success, encoded = cv2.imencode(
            ".jpg",
            atlas,
            [int(cv2.IMWRITE_JPEG_QUALITY), 92],
        )
        if not success:
            raise RuntimeError(f"Unable to write {output_path}")
        encoded.tofile(str(output_path))
        outputs.append(str(output_path))

    print(
        json.dumps(
            {"success": True, "pages": len(outputs), "outputs": outputs},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
