"""FFmpeg video rendering for clip-cutter."""

import subprocess
import threading
from pathlib import Path

from .models import Clip
from .utils import ProgressBar


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def parse_ffmpeg_time(time_str: str) -> float:
    """Parse FFmpeg time string (HH:MM:SS.ms) to seconds."""
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0


def render_clip(
    video_path: Path,
    clip: Clip,
    output_dir: Path,
    captions_path: Path | None = None,
) -> Path:
    """
    Render a single vertical clip with FFmpeg.

    Args:
        video_path: Path to source video
        clip: Clip metadata
        output_dir: Directory to save rendered clip
        captions_path: Optional path to ASS subtitle file for burned-in captions

    Returns:
        Path to rendered clip
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"clip_{clip.index}_{clip.platform}.mp4"

    print(f"\nClip {clip.index} ({clip.platform}):")

    # Build filter complex: blurred background + sharp foreground centered
    filter_parts = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg]",
        "[0:v]scale=1080:-1[fg]",
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[main]",
    ]

    # Add captions if provided
    if captions_path and captions_path.exists():
        # Escape path for FFmpeg (handle Windows paths and special chars)
        escaped_path = str(captions_path).replace("\\", "/").replace(":", "\\:")
        filter_parts.append(f"[main]ass='{escaped_path}'[out]")
        final_output = "[out]"
    else:
        final_output = "[main]"
        # Remove [main] label from last filter if no captions
        filter_parts[2] = "[bg][fg]overlay=(W-w)/2:(H-h)/2"

    filter_complex = ";".join(filter_parts)

    # Add 0.5s padding at the end to prevent audio cutting off mid-word
    end_padding = 0.5
    clip_duration = (clip.end - clip.start) + end_padding

    cmd = [
        "ffmpeg", "-y",
        "-accurate_seek",
        "-ss", str(clip.start),
        "-i", str(video_path),
        "-t", str(clip_duration),
        "-filter_complex", filter_complex,
    ]

    # Map the correct output stream (with or without captions)
    if captions_path and captions_path.exists():
        cmd.extend(["-map", "[out]", "-map", "0:a?"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(output_path),
    ])

    duration = clip.end - clip.start
    progress_bar = ProgressBar(duration, prefix="🎬 ")
    progress_bar.update(0)

    # Collect stderr in background thread to prevent deadlock
    stderr_output = []

    def drain_stderr(pipe):
        for line in pipe:
            stderr_output.append(line)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Start background thread to drain stderr
        stderr_thread = threading.Thread(target=drain_stderr, args=(process.stderr,))
        stderr_thread.daemon = True
        stderr_thread.start()

        # Parse FFmpeg progress output from stdout
        for line in process.stdout:
            if line.startswith("out_time="):
                time_str = line.split("=")[1].strip()
                if time_str and time_str != "N/A":
                    current_time = parse_ffmpeg_time(time_str)
                    progress_bar.update(current_time)

        process.wait()
        stderr_thread.join(timeout=5)
        progress_bar.finish()

        if process.returncode != 0:
            stderr_str = "".join(stderr_output)
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr_str.encode())

        print(f"   ✅ Saved: {output_path.name}")

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "".join(stderr_output)
        print(f"\n   ❌ FFmpeg error: {stderr[-500:]}")
        raise

    # Save LinkedIn caption if present
    if clip.caption and clip.platform == "linkedin":
        caption_path = output_dir / f"clip_{clip.index}_caption.txt"
        caption_path.write_text(clip.caption, encoding="utf-8")
        print(f"   📝 Caption saved: {caption_path.name}")

    return output_path
