"""Request and response shapes. Write bodies reject unknown fields."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Str = Annotated[str, StringConstraints(strip_whitespace=True)]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------

class SignupIn(In):
    email: EmailStr
    password: str = Field(max_length=128)
    display_name: Annotated[Str, StringConstraints(max_length=80)] | None = None


class LoginIn(In):
    email: EmailStr
    password: str = Field(max_length=128)


class EmailIn(In):
    email: EmailStr


class TokenIn(In):
    token: str = Field(min_length=10, max_length=200)


class ResetIn(In):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)


# ---------- users ----------

class UserOut(Out):
    id: uuid.UUID
    email: str | None
    email_verified: bool
    display_name: str | None
    avatar_url: str | None
    timezone: str
    digest_daily: bool
    digest_weekly: bool
    digest_hour: int
    memory_enabled: bool = True
    has_password: bool = False
    is_admin: bool = False
    created_at: datetime


class UserPatch(In):
    display_name: Annotated[Str, StringConstraints(max_length=80)] | None = None
    timezone: str | None = None
    digest_daily: bool | None = None
    digest_weekly: bool | None = None
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    memory_enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("unknown time zone")
        return value


class DeleteAccountIn(In):
    confirm: Literal["DELETE"]
    password: str | None = Field(default=None, max_length=128)


# ---------- canvases ----------

class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    zoom: float = Field(gt=0.02, le=8)


class CanvasIn(In):
    title: Annotated[Str, StringConstraints(min_length=1, max_length=120)] = "Untitled"
    template: Annotated[str, StringConstraints(max_length=40)] | None = None


class CanvasPatch(In):
    title: Annotated[Str, StringConstraints(min_length=1, max_length=120)] | None = None
    viewport: Viewport | None = None


class CanvasOut(Out):
    id: uuid.UUID
    title: str
    viewport: dict
    item_count: int = 0
    preview: list[dict] = []
    share_token: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------- items ----------

Kind = Literal["link", "note", "text", "code", "image"]


class LinkContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=2048)
    comment: str = Field(default="", max_length=2000)


class NoteContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str = Field(default="", max_length=20000)
    color: Literal["yellow", "blue", "green", "pink", "plain"] = "yellow"


class TextContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=2000)
    size: Literal["s", "m", "l", "xl"] = "m"


class CodeContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(default="plaintext", max_length=32)
    source: str = Field(default="", max_length=20000)
    filename: str = Field(default="", max_length=120)


class ImageContentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caption: str = Field(default="", max_length=300)


CONTENT_MODELS: dict[str, type[BaseModel]] = {
    "link": LinkContent, "note": NoteContent, "text": TextContent, "code": CodeContent, "image": ImageContentPatch,
}


class Geometry(BaseModel):
    x: float = Field(ge=-1e7, le=1e7)
    y: float = Field(ge=-1e7, le=1e7)
    w: float | None = Field(default=None, gt=0, le=1e5)
    h: float | None = Field(default=None, gt=0, le=1e5)
    z: int = Field(default=0, ge=-1_000_000, le=1_000_000)


class ItemIn(Geometry):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None  # the client may choose the id, so it can reference the card before the reply
    kind: Literal["link", "note", "text", "code"]
    content: dict[str, Any]


class ItemPatch(In):
    id: uuid.UUID
    version: int
    x: float | None = Field(default=None, ge=-1e7, le=1e7)
    y: float | None = Field(default=None, ge=-1e7, le=1e7)
    w: float | None = Field(default=None, gt=0, le=1e5)
    h: float | None = Field(default=None, gt=0, le=1e5)
    z: int | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    content: dict[str, Any] | None = None


class ItemBatch(In):
    items: list[ItemPatch] = Field(min_length=1, max_length=200)


class ItemOut(Out):
    id: uuid.UUID
    canvas_id: uuid.UUID
    kind: str
    x: float
    y: float
    w: float | None
    h: float | None
    z: int
    content: dict
    version: int
    index_state: str
    safety_state: str
    safety_categories: list[str]
    ai: dict = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("ai", mode="before")
    @classmethod
    def _public_ai(cls, value: object) -> dict:
        """Summary and tags only. The rest of the reader's notes stay in the search index."""
        raw = value if isinstance(value, dict) else {}
        tags: list[str] = []
        for tag in raw.get("tags") or []:
            text = " ".join(str(tag).split()).lower().lstrip("#")[:32]
            if text and text not in tags:
                tags.append(text)
        return {"summary": " ".join(str(raw.get("summary") or "").split())[:600], "tags": tags[:8]}


# ---------- uploads ----------

class UploadIn(In):
    filename: Annotated[Str, StringConstraints(min_length=1, max_length=200)]
    mime: Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
    bytes: int = Field(gt=0)
    x: float = Field(ge=-1e7, le=1e7)
    y: float = Field(ge=-1e7, le=1e7)
    caption: str = Field(default="", max_length=300)


# ---------- chat ----------

class ChatIn(In):
    question: Annotated[Str, StringConstraints(min_length=1, max_length=2000)]
    canvas_id: uuid.UUID | None = None
    scope: Literal["canvas", "all"] = "canvas"


# ---------- reminders ----------

class ChatActionIn(In):
    action: Literal["save_note", "checklist"]
    canvas_id: uuid.UUID
    x: float = Field(default=0, ge=-1e7, le=1e7)
    y: float = Field(default=0, ge=-1e7, le=1e7)


class ReminderIn(In):
    remind_at: datetime
    item_id: uuid.UUID | None = None
    note: Annotated[Str, StringConstraints(max_length=500)] = ""


class ReminderPatch(In):
    remind_at: datetime | None = None
    note: Annotated[Str, StringConstraints(max_length=500)] | None = None


class ReminderOut(Out):
    id: uuid.UUID
    item_id: uuid.UUID | None
    canvas_id: uuid.UUID | None
    note: str
    remind_at: datetime
    state: str
    sent_at: datetime | None
    created_at: datetime


def data(value: Any) -> dict:
    return {"data": value}


def page(items: list, limit: int, next_cursor: str | None) -> dict:
    return {"data": items, "page": {"limit": limit, "next_cursor": next_cursor}}
