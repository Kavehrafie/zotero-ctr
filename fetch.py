from pyzotero import zotero

from models import Attachment, Creator, Item


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


def load_library() -> tuple[list[Item], list[Attachment]]:
    z = zotero.Zotero("0", "user", local=True)
    entries = [raw["data"] for raw in z.everything(z.items())]
    items = [to_item(d) for d in entries if d["itemType"] not in ("attachment", "note")]
    attachments = [
        to_attachment(d)
        for d in entries
        if d["itemType"] == "attachment" and d.get("md5")
    ]
    return items, attachments
