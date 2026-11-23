"""Planners: pure decisions, returned as data."""

from typing import NamedTuple

from execute import dir_size
from grouping import pick_master
from models import Attachment, Item


class Write(NamedTuple):
    key: str
    changes: dict


class Trash(NamedTuple):
    key: str


class SplitCreators(NamedTuple):
    key: str


class FreeLocal(NamedTuple):
    key: str
    size: int


Command = Write | Trash | SplitCreators | FreeLocal

FILLABLE = {"title": "title", "doi": "DOI", "publisher": "publisher"}


def plan_merge(
    master: Item, dups: list[Item], attachments: list[Attachment]
) -> list[Trash | Write]:
    """Reparent dups' attachments, fill the master's empty fields, trash the dups."""
    dup_keys = {d.key for d in dups}
    plan = [
        Write(a.key, {"parentItem": master.key})
        for a in attachments
        if a.parent_key in dup_keys
    ]
    filled: set[str] = set()
    for dup in dups:
        changes = {}
        for attr, field in FILLABLE.items():
            value = getattr(dup, attr)
            if value and attr not in filled and not getattr(master, attr):
                changes[field] = value
                filled.add(attr)
            if changes:
                plan.append(Write(master.key, changes))
    plan += [Trash(d.key) for d in dups]

    return plan


def plan_delete(members: list[Item]) -> list[Command]:
    """Keep the master, trash every other member."""
    master = pick_master(members)
    return [Trash(e.key) for e in members if e is not master]


def plan_free(items, children: dict[str, list], storage_root) -> list[Command]:
    """Free the local folder of every attachment that has one on disk."""
    plan = []
    for it in items:
        for att in children.get(it.key, []):
            path = storage_root / att.key
            if path.exists():
                plan.append(FreeLocal(att.key, dir_size(path)))
    return plan


def describe(command: Command) -> str:
    """One dry-run line per command – the plan, printed."""
    if isinstance(command, Write):
        return f"write {command.key}: {', '.join(sorted(command.changes))}"
    if isinstance(command, Trash):
        return f"trash {command.key}"
    if isinstance(command, SplitCreators):
        return f"split creators {command.key}"
    return f"free {command.key} ({command.size / 1e6:.1f} MB)"
