import sqlite3
from pathlib import Path

from pyzotero import zotero

from models import Attachment, Creator, Item

DB = Path.home() / "Zotero" / "zotero.sqlite"
SKIP_TYPES = {"note", "attachment"}
PAGE_ITEMS = 500


def fetch_library() -> tuple[list[Item], list[Attachment]]:
    """Read Zotero's own database: the snapshot is always current."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    types = dict(conn.execute("SELECT itemTypeID, typeName FROM itemTypes"))
    trashed = {r[0] for r in conn.execute("SELECT itemID FROM deletedItems")}
    key_of = dict(conn.execute("SELECT itemID, key FROM items"))

    data: dict[int, dict] = {}
    for item_id, field, value in conn.execute(
        "SELECT id.itemID, f.fieldName, v.value FROM itemData id "
        "JOIN fields f ON f.fieldID = id.fieldID "
        "JOIN itemDataValues v ON v.valueID = id.valueID"
    ):
        data.setdefault(item_id, {})[field] = value

    creators: dict[int, list[Creator]] = {}
    for item_id, first, last in conn.execute(
        "SELECT ic.itemID, c.firstName, c.lastName FROM itemCreators ic "
        "JOIN creators c ON c.creatorID = ic.creatorID "
        "ORDER BY ic.itemID, ic.orderIndex"
    ):
        creators.setdefault(item_id, []).append(
            Creator(first=first or "", last=last or "")
        )

    tags: dict[int, list[str]] = {}
    for item_id, name in conn.execute(
        "SELECT it.itemID, t.name FROM itemTags it JOIN tags t ON t.tagID = it.tagID"
    ):
        tags.setdefault(item_id, []).append(name)

    items = []
    for item_id, key, version, type_id in conn.execute(
        "SELECT itemID, key, version, itemTypeID FROM items WHERE libraryID = 1"
    ):
        if item_id in trashed or types[type_id] in SKIP_TYPES:
            continue
        d = data.get(item_id, {})
        crew = creators.get(item_id, [])
        items.append(
            Item(
                key=key,
                version=version or 0,
                title=d.get("title", ""),
                item_type=types[type_id],
                year=d.get("date"),
                doi=d.get("DOI") or None,
                publisher=d.get("publisher", ""),
                creators=[f"{c.first} {c.last}".strip() for c in crew],
                tags=tags.get(item_id, []),
                creator=crew[0] if crew else Creator(),
            )
        )

    attachments = [
        Attachment(
            key=key,
            version=version or 0,
            filename=path.removeprefix("storage:"),
            md5=storage_hash or "",
            parent_key=key_of.get(parent_id, ""),
            content_type=content_type,
        )
        for (item_id, key, version, parent_id, path, storage_hash, content_type) in conn.execute(
            "SELECT i.itemID, i.key, i.version, ia.parentItemID, ia.path, ia.storageHash, ia.contentType "
            "FROM itemAttachments ia JOIN items i ON i.itemID = ia.itemID "
            "WHERE i.libraryID = 1"
        )
        if storage_hash and item_id not in trashed
    ]
    return items, attachments


def zotero_client(local_api_key: str = ""):
    return zotero.Zotero("0", "user", local=True, local_api_key=local_api_key)


def fetch_library_api() -> tuple[list[Item], list[Attachment]]:
    """The old pyzotero path -- the escape hatch if a Zotero upgrade shifts the schema."""
    z = zotero_client()
    entries = [
        raw["data"] for raw in z.everything(z.items(limit=PAGE_ITEMS, itemType="-attachment"))
    ]
    atts = [
        raw["data"] for raw in z.everything(z.items(limit=PAGE_ITEMS, itemType="attachment"))
    ]
    items = [to_item(d) for d in entries if d["itemType"] != "note"]
    attachments = [to_attachment(d) for d in atts if d.get("md5")]
    return items, attachments


def to_item(d) -> Item:
    first = next(iter(d.get("creators") or [{}]))
    return Item(
        key=d["key"],
        version=d.get("version", 0),
        title=d.get("title") or "",
        item_type=d.get("itemType") or "",
        year=d.get("date"),
        doi=d.get("DOI") or None,
        publisher=d.get("publisher") or "",
        creators=[
            f"{c.get('firstName', '')} {c.get('lastName', '') or c.get('name', '')}".strip()
            for c in d.get("creators") or []
        ],
        tags=[t["tag"] for t in d.get("tags") or []],
        creator=Creator(
            first=first.get("firstName", ""),
            last=first.get("lastName") or first.get("name", ""),
        ),
    )


def to_attachment(d) -> Attachment:
    return Attachment(
        key=d["key"],
        version=d.get("version", 0),
        filename=d.get("filename") or "",
        md5=d["md5"],
        parent_key=d.get("parentItem") or "",
        content_type=d.get("contentType", ""),
    )


def load_library(api: bool = False) -> tuple[list[Item], list[Attachment]]:
    return fetch_library_api() if api else fetch_library()
