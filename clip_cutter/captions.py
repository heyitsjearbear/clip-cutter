"""Caption generation using AssemblyAI with TikTok-style word highlighting."""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .utils import Spinner


@dataclass
class WordTimestamp:
    """A word with its timing information."""

    text: str
    start: float  # seconds
    end: float  # seconds
    confidence: float


@dataclass
class TranscriptionResult:
    """Result of transcribing audio."""

    words: list[WordTimestamp]
    full_text: str


def extract_audio_segment(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path | None = None,
) -> Path:
    """
    Extract audio segment from video using FFmpeg.

    Args:
        video_path: Path to source video
        start: Start time in seconds
        end: End time in seconds
        output_path: Optional output path (creates temp file if None)

    Returns:
        Path to extracted audio file
    """
    if output_path is None:
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        output_path = Path(temp_path)

    duration = end - start

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", str(video_path),
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # PCM 16-bit
        "-ar", "16000",  # 16kHz sample rate (optimal for speech)
        "-ac", "1",  # Mono
        str(output_path),
    ]

    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def transcribe_with_assemblyai(audio_path: Path) -> TranscriptionResult:
    """
    Transcribe audio using AssemblyAI API.

    Args:
        audio_path: Path to audio file

    Returns:
        TranscriptionResult with word-level timestamps
    """
    import assemblyai as aai

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError(
            "ASSEMBLYAI_API_KEY not set in environment. "
            "Get one at https://www.assemblyai.com/"
        )

    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        language_code="en",
    )

    import time
    start_time = time.time()

    try:
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(str(audio_path), config=config)
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ASSEMBLYAI API ERROR (transcription)")
        print(f"   Elapsed time: {elapsed:.1f}s before failure")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        raise

    if transcript.status == aai.TranscriptStatus.error:
        elapsed = time.time() - start_time
        print(f"\n❌ ASSEMBLYAI TRANSCRIPTION ERROR")
        print(f"   Elapsed time: {elapsed:.1f}s")
        print(f"   Error: {transcript.error}")
        raise RuntimeError(f"Transcription failed: {transcript.error}")

    words = []
    for word in transcript.words or []:
        words.append(
            WordTimestamp(
                text=word.text,
                start=word.start / 1000.0,  # Convert ms to seconds
                end=word.end / 1000.0,
                confidence=word.confidence,
            )
        )

    return TranscriptionResult(
        words=words,
        full_text=transcript.text or "",
    )


def transcribe_clip(
    video_path: Path,
    start: float,
    end: float,
) -> TranscriptionResult:
    """
    Extract audio from video clip and transcribe with AssemblyAI.

    Args:
        video_path: Path to source video
        start: Clip start time in seconds
        end: Clip end time in seconds

    Returns:
        TranscriptionResult with word-level timestamps (relative to clip start)
    """
    spinner = Spinner("Extracting audio...")
    spinner.start()

    try:
        audio_path = extract_audio_segment(video_path, start, end)
        spinner.stop("✅ Audio extracted")
    except Exception as e:
        spinner.stop(f"❌ Audio extraction failed: {e}")
        raise

    spinner = Spinner("Transcribing with AssemblyAI...")
    spinner.start()

    try:
        result = transcribe_with_assemblyai(audio_path)
        spinner.stop(f"✅ Transcribed: {len(result.words)} words")

        # Clean up temp audio file
        audio_path.unlink(missing_ok=True)

        return result
    except Exception as e:
        spinner.stop(f"❌ Transcription failed: {e}")
        audio_path.unlink(missing_ok=True)
        raise


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs % 1) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


def generate_ass_subtitles(
    words: list[WordTimestamp],
    style: str = "tiktok",
    chars_per_line: int = 32,
) -> str:
    """
    Generate ASS subtitle file content with word-by-word highlighting.

    Args:
        words: List of words with timing info
        style: "standard" or "tiktok" (karaoke highlighting with pop effect)
        chars_per_line: Max characters before line break

    Returns:
        Complete ASS file content as string
    """
    # Caption positioning:
    # - Video frame: 1080x1920 (portrait)
    # - 16:9 video centered: 1080x608, bottom edge at 1264px from top
    # - MarginV=560 puts caption bottom at 1920-560=1360px (96px below video)
    caption_margin_v = 560

    if style == "tiktok":
        # TikTok style: Bold, positioned below video, with pop effect
        # Accent color: #2563EB (blue) -> ASS BGR format: &HEB6325&
        header = f"""[Script Info]
Title: TikTok Style Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,64,&H00FFFFFF,&HEB6325,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,1,4,2,2,20,20,{caption_margin_v},1
Style: Active,Arial Black,64,&HEB6325,&HEB6325,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,1,4,2,2,20,20,{caption_margin_v},1
Style: Inactive,Arial Black,52,&H80FFFFFF,&H80FFFFFF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,1,4,2,2,20,20,{caption_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    else:
        # Standard style: Simple white text, positioned below video
        header = f"""[Script Info]
Title: Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,20,20,{caption_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    if style == "tiktok":
        # Generate pop effect with per-word scaling
        events = _generate_pop_karaoke_events(words, chars_per_line)
    else:
        # Standard: Show phrases without highlighting
        events = _generate_standard_events(words, chars_per_line)

    return header + "\n".join(events)


def _generate_pop_karaoke_events(
    words: list[WordTimestamp],
    chars_per_line: int,
) -> list[str]:
    """
    Generate karaoke events with pop effect - active word scales up.

    Each phrase is shown with all words visible, but the active word
    is highlighted (blue) and scaled larger. Captions stay on screen
    continuously within a chunk - no flashing during pauses.
    """
    events = []

    # Group words into display chunks
    chunks = _group_words_into_chunks(words, chars_per_line)

    for chunk in chunks:
        if not chunk:
            continue

        chunk_end = chunk[-1].end

        # For each word in the chunk, create events showing all words
        # with the current word highlighted and scaled
        for i, active_word in enumerate(chunk):
            word_start = active_word.start

            # Event extends until NEXT word starts (not when current word ends)
            # This prevents flashing/disappearing during pauses in speech
            if i < len(chunk) - 1:
                # Not the last word: extend to next word's start
                event_end = chunk[i + 1].start
            else:
                # Last word in chunk: extend to chunk end
                event_end = chunk_end

            # Calculate animation duration based on actual word duration (not event duration)
            word_duration_ms = int((active_word.end - active_word.start) * 1000)
            pop_in = min(80, max(40, word_duration_ms // 4))  # Quick pop in
            pop_out = min(80, max(40, word_duration_ms // 4))  # Quick pop out
            hold_time = max(0, word_duration_ms - pop_in - pop_out)

            # Build the text with all words, highlighting the active one
            text_parts = []
            for j, word in enumerate(chunk):
                if j == i:
                    # Active word: blue #2563EB (ASS BGR: &HEB6325&), scaled up with pop animation
                    text_parts.append(
                        f"{{\\c&HEB6325&\\fscx100\\fscy100"
                        f"\\t(0,{pop_in},\\fscx130\\fscy130)"
                        f"\\t({pop_in + hold_time},{word_duration_ms},\\fscx100\\fscy100)}}"
                        f"{word.text}"
                    )
                else:
                    # Inactive word: white, normal size, slightly transparent
                    text_parts.append(f"{{\\c&HFFFFFF&\\fscx85\\fscy85\\alpha&H40&}}{word.text}")

            text = " ".join(text_parts)

            # Create dialogue event - extends to next word start (no gaps)
            start_time = format_ass_time(word_start)
            end_time = format_ass_time(event_end)

            event = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
            events.append(event)

    return events


def _generate_standard_events(
    words: list[WordTimestamp],
    chars_per_line: int,
) -> list[str]:
    """Generate standard subtitle events without highlighting."""
    events = []

    chunks = _group_words_into_chunks(words, chars_per_line)

    for chunk in chunks:
        if not chunk:
            continue

        start_time = format_ass_time(chunk[0].start)
        end_time = format_ass_time(chunk[-1].end)

        text = " ".join(w.text for w in chunk)

        event = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
        events.append(event)

    return events


def _group_words_into_chunks(
    words: list[WordTimestamp],
    chars_per_line: int,
) -> list[list[WordTimestamp]]:
    """Group words into display chunks based on character limit."""
    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        word_length = len(word.text) + 1  # +1 for space

        if current_length + word_length > chars_per_line and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0

        current_chunk.append(word)
        current_length += word_length

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def create_captions_for_clip(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    output_path: Path,
    style: str = "tiktok",
    chars_per_line: int = 32,
) -> Path:
    """
    Create ASS caption file for a video clip.

    Args:
        video_path: Path to source video
        clip_start: Clip start time in seconds
        clip_end: Clip end time in seconds
        output_path: Path to save ASS file
        style: Caption style ("standard" or "tiktok")
        chars_per_line: Max characters per caption line

    Returns:
        Path to created ASS file
    """
    # Transcribe the clip
    result = transcribe_clip(video_path, clip_start, clip_end)

    if not result.words:
        print("   ⚠️  No words detected in audio")
        # Create empty ASS file
        output_path.write_text(generate_ass_subtitles([], style), encoding="utf-8")
        return output_path

    # Generate ASS content
    ass_content = generate_ass_subtitles(
        result.words,
        style=style,
        chars_per_line=chars_per_line,
    )

    # Save to file
    output_path.write_text(ass_content, encoding="utf-8")
    print(f"   📝 Captions saved: {output_path.name}")

    return output_path
