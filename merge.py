from models import Attachment, Item


STRUCTURAL = {
    "key",
    "version",
    "itemType",
    "parentItem",
    "collections",
    "relations",
    "tags",
    "deleted",
}


def merge_group(
    z, master: Item, dups: list[Item], attachments: list[Attachment]
) -> str:
    dup_keys = {d.key for d in dups}
    moved = 0
    for att in attachments:
        if att.parent_key in dup_keys:
            z.update_item(
                {"key": att.key, "version": att.version}, {"parentItem": master.key}
            )
            moved += 1
    master_data = z.item(master.key)["data"]
    changes = {}
    for dup in dups:
        for field, value in z.item(dup.key)["data"].items():
            if (
                field not in STRUCTURAL
                and value
                and field in master_data
                and not master_data.get(field)
            ):
                changes.setdefault(field, value)

    if changes:
        z.update_item({"key": master.key, "version": master_data["version"]}, changes)

    z.update_items({"key": d.key, "version": d.version, "deleted": 1} for d in dups)

    return f"{master.key} absorbed {len(dups)} dup(s): {moved} attachment(s) reparented, {len(changes)} field(s) filled"
