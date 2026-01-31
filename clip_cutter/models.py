"""Data models for clip-cutter."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Clip:
    """Represents a video clip to be extracted."""

    index: int
    start: float  # seconds
    end: float  # seconds
    transcript: str  # the words in this clip
    # Viral clip fields (clip_extraction.txt)
    platform: Optional[str] = None  # "tiktok" | "youtube_shorts" | "reels" | "linkedin"
    hook: Optional[str] = None  # the attention-grabbing opener
    caption: Optional[str] = None  # LinkedIn caption (only for linkedin clips)
    # Demo highlight fields (demo_highlights.txt)
    moment_type: Optional[str] = None  # "customer_reaction" | "feature_reveal" | etc.

    @property
    def duration(self) -> int:
        return int(self.end - self.start)
