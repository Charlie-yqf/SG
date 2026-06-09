#!/usr/bin/env python3
"""Export SpatialGen per-view RGB images as a numbered frame sequence."""

# 中文说明：这个脚本只整理 SpatialGen 已导出的 rgb_*.png，
# 把它们复制成 frame_00000.png 这种连续帧命名，方便后续交给 Wan/插帧模型。

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image


RGB_RE = re.compile(r"^rgb_(\d+)\.png$")
ROUND_RE = re.compile(r"^round_(\d+)$")


def numeric_key(path: Path) -> tuple[int, int]:
    round_match = ROUND_RE.match(path.parent.name)
    rgb_match = RGB_RE.match(path.name)
    round_idx = int(round_match.group(1)) if round_match else 0
    rgb_idx = int(rgb_match.group(1)) if rgb_match else 0
    return round_idx, rgb_idx


def find_rgb_frames(input_path: Path) -> list[Path]:
    if input_path.is_file():
        raise ValueError(f"Expected a directory, got file: {input_path}")

    direct = sorted(
        [p for p in input_path.glob("rgb_*.png") if RGB_RE.match(p.name)],
        key=numeric_key,
    )
    if direct:
        return direct

    frames: list[Path] = []
    round_dirs = sorted(
        [p for p in input_path.glob("round_*") if p.is_dir() and ROUND_RE.match(p.name)],
        key=lambda p: int(ROUND_RE.match(p.name).group(1)),
    )
    for round_dir in round_dirs:
        frames.extend(
            sorted(
                [p for p in round_dir.glob("rgb_*.png") if RGB_RE.match(p.name)],
                key=numeric_key,
            )
        )
    return frames


def validate_image(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def export_frames(input_path: Path, output_dir: Path, overwrite: bool) -> list[Path]:
    frames = find_rgb_frames(input_path)
    if not frames:
        raise RuntimeError(f"No rgb_*.png files found under {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for idx, src in enumerate(frames):
        validate_image(src)
        dst = output_dir / f"frame_{idx:05d}.png"
        if dst.exists() and not overwrite:
            raise FileExistsError(f"{dst} exists; pass --overwrite to replace it")
        shutil.copy2(src, dst)
        exported.append(dst)
    return exported


def make_video(frames_dir: Path, output_video: Path, fps: int, overwrite: bool) -> None:
    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%05d.png"),
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        str(output_video),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect SpatialGen rgb_*.png outputs into frame_00000.png style sequence."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="A SpatialGen round directory or room output directory, e.g. out/.../val/scene_00000/round_0.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Directory for numbered frames.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing numbered frames/video.")
    parser.add_argument("--make-video", action="store_true", help="Also create an MP4 preview with ffmpeg.")
    parser.add_argument("--fps", type=int, default=4, help="Preview video frame rate.")
    parser.add_argument("--video", type=Path, default=None, help="Output MP4 path. Defaults to OUTPUT/preview.mp4.")
    args = parser.parse_args()

    frames = export_frames(args.input, args.output, overwrite=args.overwrite)
    print(f"Exported {len(frames)} frames to {args.output}")

    if args.make_video:
        output_video = args.video or args.output / "preview.mp4"
        make_video(args.output, output_video, fps=args.fps, overwrite=args.overwrite)
        print(f"Wrote preview video to {output_video}")


if __name__ == "__main__":
    main()
