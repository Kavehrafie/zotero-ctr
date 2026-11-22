import json
import time
from pathlib import Path

from pyzotero import zotero

from models import Attachment, Creator, Item

CACHE_FILE = Path(".zotero-cache.json")
CACHE_TTL_SECONDS = 3600


def to_item(d) -> Item:
    first = next(iter(d.get("creators") or [{}]))
    return Item(
        key=d["key"],
        title=d.get("title") or "Untitled",
        year=d.get("date"),
        doi=d.get("DOI") or None,
        creator=Creator(
            first=first.get("firstName", ""),
            last=first.get("lastName") or first.get("name", ""),
        ),
    )


def to_attachment(d) -> Attachment:
    return Attachment(
        key=d["key"],
        filename=d.get("filename") or "",
        md5=d["md5"],
        parent_key=d.get("parentItem") or "",
    )


def fetch_library() -> tuple[list[Item], list[Attachment]]:
    z = zotero.Zotero("0", "user", local=True)
    entries = [raw["data"] for raw in z.everything(z.items())]
    items = [to_item(d) for d in entries if d["itemType"] not in ("attachment", "note")]
    attachments = [
        to_attachment(d)
        for d in entries
        if d["itemType"] == "attachment" and d.get("md5")
    ]
    return items, attachments


def save_cache(items, attachments) -> None:
    payload = {
        "items": [i.model_dump() for i in items],
        "attachments": [a.model_dump() for a in attachments],
    }
    CACHE_FILE.write_text(json.dumps(payload))


def load_cache() -> tuple[list[Item], list[Attachment]]:
    data = json.loads(CACHE_FILE.read_text())
    return (
        [Item.model_validate(d) for d in data["items"]],
        [Attachment.model_validate(d) for d in data["attachments"]],
    )


def cache_fresh() -> bool:
    return (
        CACHE_FILE.exists()
        and time.time() - CACHE_FILE.stat().st_mtime < CACHE_TTL_SECONDS
    )


def load_library(refresh: bool = False) -> tuple[list[Item], list[Attachment]]:
    if not refresh and cache_fresh():
        return load_cache()
    items, attachments = fetch_library()
    save_cache(items, attachments)
    return items, attachments
