"""Data models for clip-cutter."""

from dataclasses import dataclass


@dataclass
class Clip:
    """Represents a video clip to be extracted."""

    index: int
    platform: str  # "tiktok" | "youtube_shorts" | "reels" | "linkedin"
    start: float  # seconds
    end: float  # seconds
    transcript: str  # the words in this clip
    hook: str  # the attention-grabbing opener
    caption: str | None  # LinkedIn caption (only for linkedin clips)

    @property
    def duration(self) -> int:
        return int(self.end - self.start)
