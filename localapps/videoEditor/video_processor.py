import os
import re
import json
import subprocess
from typing import List, Tuple


def get_video_info(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])
    video_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "video"), None
    )
    audio_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "audio"), None
    )
    return {
        "duration": duration,
        "width": int(video_stream.get("width", 1280)) if video_stream else 1280,
        "height": int(video_stream.get("height", 720)) if video_stream else 720,
        "has_audio": audio_stream is not None,
    }


def detect_scene_changes(video_path: str, threshold: float = 0.3) -> List[float]:
    """FFmpeg scene detection — returns timestamps (seconds) of detected cuts."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr", "-an", "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    timestamps: List[float] = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line and "showinfo" in line:
            m = re.search(r"pts_time:([\d.]+)", line)
            if m:
                t = float(m.group(1))
                if t > 0.5:
                    timestamps.append(t)
    return sorted(set(timestamps))


def detect_silence_midpoints(video_path: str, noise_db: int = -35, min_dur: float = 0.6) -> List[float]:
    """Audio silence detection — returns midpoints of silent gaps as potential cuts."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", f"silencedetect=n={noise_db}dB:d={min_dur}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    midpoints: List[float] = []
    starts: List[float] = []
    for line in result.stderr.split("\n"):
        if "silence_start:" in line:
            m = re.search(r"silence_start: ([\d.]+)", line)
            if m:
                starts.append(float(m.group(1)))
        elif "silence_end:" in line and starts:
            m = re.search(r"silence_end: ([\d.]+)", line)
            if m:
                end = float(m.group(1))
                start = starts.pop()
                if end - start < 5.0:  # skip very long silences (black cards etc.)
                    midpoints.append((start + end) / 2)
    return sorted(midpoints)


def compute_logical_segments(
    video_path: str,
    scene_threshold: float = 0.3,
    max_segments: int = 8,
) -> List[dict]:
    """
    Combine scene + silence detection into logical segments.
    Returns list of {index, start, end, duration}.
    """
    info = get_video_info(video_path)
    duration = info["duration"]

    scene_cuts = detect_scene_changes(video_path, scene_threshold)
    silence_cuts = detect_silence_midpoints(video_path) if info["has_audio"] else []

    # Merge candidates, collapse those within 1 s of each other
    all_cuts = sorted(set(scene_cuts + silence_cuts))
    merged: List[float] = []
    last = -2.0
    for t in all_cuts:
        if t - last > 1.0:
            merged.append(t)
            last = t

    # Respect max_segments cap
    if len(merged) >= max_segments:
        step = len(merged) / (max_segments - 1)
        indices = [int(i * step) for i in range(max_segments - 1)]
        merged = [merged[min(i, len(merged) - 1)] for i in indices]

    boundaries = [0.0] + merged + [duration]
    segments: List[dict] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end - start >= 0.5:
            segments.append({
                "index": len(segments),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
            })
    return segments


def _normalize_segment(src: str, start: float, duration: float, dest: str) -> str:
    """Extract and re-encode a segment to h264/aac at 1280x720 30fps."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-i", src, "-t", str(duration),
        "-vf", (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
        ),
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-shortest",
        dest,
    ]
    subprocess.run(cmd, capture_output=True, timeout=180)
    return dest


def interleave_and_merge(
    v1_path: str,
    v1_segments: List[dict],
    v2_path: str,
    v2_segments: List[dict],
    output_path: str,
    work_dir: str,
) -> str:
    """
    Interleave v1 and v2 segments:
      [V1_0, V2_0, V1_1, V2_1, ..., V1_N]
    Re-encodes all pieces to a common format before concat.
    """
    os.makedirs(work_dir, exist_ok=True)
    normalized: List[str] = []

    def _add(src_path: str, seg: dict, label: str, idx: int) -> None:
        dest = os.path.join(work_dir, f"{label}_{idx:03d}.mp4")
        _normalize_segment(src_path, seg["start"], seg["duration"], dest)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            normalized.append(dest)

    n1 = len(v1_segments)
    n2 = len(v2_segments)

    for i, seg in enumerate(v1_segments):
        _add(v1_path, seg, "v1", i)
        # Insert v2 between every v1 segment (not after the last)
        if i < n1 - 1 and n2 > 0:
            _add(v2_path, v2_segments[i % n2], "v2", i)

    # Build concat list and merge
    concat_file = os.path.join(work_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for p in normalized:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Merge failed: {result.stderr.decode()[-500:]}")

    return output_path
