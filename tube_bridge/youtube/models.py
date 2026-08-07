"""tube-bridge — YouTube data models."""

from dataclasses import dataclass


@dataclass
class VideoInfo:
    id: str
    title: str
    url: str
    duration: int | None = None  # seconds
    view_count: int | None = None
    channel: str | None = None
    channel_url: str | None = None
    upload_date: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}
