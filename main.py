from typing import Callable

from apply import WriteFailed, apply, open_write_session
from config import load_config
from execute import dir_size
from fetch import load_library
from grouping import find_groups, pick_master
from normalize import clean_title
from plan import SplitCreators, Write, plan_delete, plan_free, plan_merge
from preview import attachment_pdf, evidence_images, first_pdf, open_pdf
from ui import SOURCES, Action, CtrApp, Evidence, MergeDialog, Session


def reporter(factory) -> Callable:
    """Wrap the applier: the write session opens on first real command;
    one rejection reports red instead of aborting the batch."""

    lazy: dict = {}

    def do(command) -> str:
        if "z" not in lazy:
            lazy["z"], lazy["cfg"] = factory()
        try:
            return apply(command, lazy["z"], lazy["cfg"])
        except WriteFailed as e:
            return f"✗ {e}"

    return do


def title_rows(items) -> tuple[list, Callable, Callable, list]:
    rows = [
        (it, clean_title(it.title))
        for it in items
        if clean_title(it.title) != it.title
    ]

    def fix_plan(proposals) -> list:
        return [Write(it.key, {"title": new}) for it, new in proposals]

    def proposal_cell(p) -> list[str]:
        it, new = p
        return [it.key, it.title, new]

    return rows, fix_plan, proposal_cell, ["key", "now", "proposed"]


def names_rows(items) -> tuple[list, Callable, Callable, list]:
    rows = [it for it in items if any(", " in c for c in it.creators)]

    def fix_plan(selected) -> list:
        return [SplitCreators(it.key) for it in selected]

    def proposal_cell(it) -> list[str]:
        return [it.key, ", ".join(it.creators)]

    return rows, fix_plan, proposal_cell, ["key", "creators"]


def review_session(what: str) -> Session:
    """Duplicate groups flattened: one row per item, labelled with its keeper."""
    library = load_library()
    src = SOURCES[what]
    entries = src.pick(library)
    groups = find_groups(entries, src.key_of)
    cfg = load_config()
    label_of = {}
    for _, members in groups.items():
        label = pick_master(members)
        name = (label.title if what == "entries" else label.filename)[:32]
        for m in members:
            label_of[m.key] = name

    def merge_ask(selected) -> MergeDialog:
        atts = {
            e.key: [a for a in library[1] if a.parent_key == e.key] for e in selected
        }
        dialog = MergeDialog(list(selected), atts, pick_master(selected))

        def build_plan(dlg) -> list:
            master = dlg.master
            others = [e for e in dlg.entries if e is not master]
            moved = [a for e, a in dlg.rows if a and dlg.fates[a.key].startswith("move")]
            return plan_merge(master, others, moved)

        dialog.build_plan = build_plan  # the dialog hands back its choices
        return dialog

    def delete_plan(selected) -> list:
        return plan_delete(selected)

    pdf_of = (
        (lambda m: first_pdf(cfg, library[1], m.key))
        if what == "entries"
        else (lambda m: attachment_pdf(cfg, m))
    )

    def evidence_screen(selected) -> Evidence:
        images = []
        for m in selected:
            path = pdf_of(m)
            if path:
                images += evidence_images(path, full=len(selected) == 1)
        return Evidence(images)

    def open_peek(selected) -> str:
        m = selected[0]
        path = pdf_of(m)
        if path:
            open_pdf(path)
        return str(path) if path else f"{m.key}: no PDF"

    item_cell = (
        (lambda m: [m.title, str(m.year or "—"), ", ".join(m.creators[:2]) or "—", label_of[m.key]])
        if what == "entries"
        else (lambda a: [a.filename, a.key, a.parent_key, label_of[a.key]])
    )
    headers = (
        ["title", "year", "creators", "dup of"]
        if what == "entries"
        else ["file", "key", "parent", "dup of"]
    )
    actions = (
        [Action("m", "merge", dialog=merge_ask)] if what == "entries" else []
    )
    actions += [
        Action("d", "delete dups", plan=delete_plan),
        Action("v", "pdf evidence", screen=evidence_screen),
        Action("o", "open", peek=open_peek),
    ]
    rows = [m for _, members in groups.items() for m in members]
    return Session(
        title="duplicate items",
        rows=rows,
        headers=headers,
        widths=(40, 6, 26, 32) if what == "entries" else (40, 12, 12, 32),
        cell=item_cell,
        actions=actions,
        do=reporter(lambda: open_write_session(True)),
    )


def free_session() -> Session:
    """Every entry with a local copy; select rows, then free them."""
    items, attachments = load_library()
    children: dict[str, list] = {}
    for att in attachments:
        children.setdefault(att.parent_key, []).append(att)
    cfg = load_config()
    rows = [
        it
        for it in items
        if any((cfg.storage_root / a.key).exists() for a in children.get(it.key, []))
    ]

    sizes = {
        it.key: sum(
            dir_size(cfg.storage_root / a.key) for a in children.get(it.key, [])
        )
        for it in rows
    }

    def item_cell(it) -> list[str]:
        return [
            it.key,
            it.title,
            ", ".join(it.creators[:2]) or "—",
            str(it.year or "—"),
            it.publisher or "—",
            f"{sizes[it.key] / 1e6:.1f} MB",
        ]

    def free_plan(selection) -> list:
        return plan_free(selection, children, cfg.storage_root)

    return Session(
        title="matched items",
        rows=rows,
        headers=["key", "title", "creator", "year", "publisher", "local"],
        widths=(12, 40, 24, 6, 22, 9),
        cell=item_cell,
        actions=[Action("f", "free", plan=free_plan)],
        do=reporter(lambda: (None, load_config())),
    )


def clean_session(what: str) -> Session:
    """Cleanup proposals for titles or creator names."""
    items, _ = load_library()
    rows, fix_plan, proposal_cell, headers = (
        title_rows if what == "title" else names_rows
    )(items)
    return Session(
        title="cleanup proposals",
        rows=rows,
        headers=headers,
        widths=(12, 36, 36),
        cell=proposal_cell,
        actions=[Action("f", "fix", plan=fix_plan)],
        do=reporter(lambda: open_write_session(True)),
    )


VIEWS = {
    "review entries": lambda: review_session("entries"),
    "review attachments": lambda: review_session("attachments"),
    "free local": lambda: free_session(),
    "clean titles": lambda: clean_session("title"),
    "clean names": lambda: clean_session("names"),
}

if __name__ == "__main__":
    CtrApp(VIEWS).run()
