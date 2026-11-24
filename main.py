from typing import Callable

import typer

from apply import WriteFailed, apply, open_write_session
from config import load_config
from execute import dir_size
from fetch import load_library
from fixtures import ATTACHMENTS, ITEMS
from grouping import find_groups, pick_master
from normalize import clean_title
from plan import SplitCreators, Write, plan_delete, plan_free, plan_merge
from preview import attachment_pdf, first_pdf, open_pdf, thumbnail
from ui import SOURCES, Action, Session, console, run

app = typer.Typer()


def is_match(it, author: str, tag: str, title: str) -> bool:
    hit = (
        (author and any(author.lower() in c.lower() for c in it.creators))
        or (tag and tag.lower() in (t.lower() for t in it.tags))
        or (title and title.lower() in it.title.lower())
    )
    return bool(hit)


def reporter(client, cfg, execute: bool):
    """Wrap the applier: one rejected write reports red instead of aborting the batch."""

    def do(command) -> str:
        if not execute:
            return "[yellow]dry run - nothing written[/yellow]"
        try:
            return apply(command, client, cfg)
        except WriteFailed as e:
            return f"[red]{e}[/red]"

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
        return [it.key, it.title[:40], new[:40]]

    return rows, fix_plan, proposal_cell, ["key", "now", "proposed"]


def names_rows(items) -> tuple[list, Callable, Callable, list]:
    rows = [it for it in items if any(", " in c for c in it.creators)]

    def fix_plan(selected) -> list:
        return [SplitCreators(it.key) for it in selected]

    def proposal_cell(it) -> list[str]:
        return [it.key, ", ".join(it.creators)[:60]]

    return rows, fix_plan, proposal_cell, ["key", "creators"]


@app.command()
def review(
    what: str = typer.Option("entries", "--what", help="entries or attachments"),
    fake: bool = typer.Option(
        False, "--fake", help="use mockup data instead of Zotero"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="re-fetch from Zotero, ignoring the cache"
    ),
    execute: bool = typer.Option(
        False, "--execute", help="apply attachment deletions; otherwise dry run"
    ),
):
    """Interactively review duplicate groups page by page (dry run unless --execute)"""
    library = (ITEMS, ATTACHMENTS) if fake else load_library(refresh)
    src = SOURCES[what]
    entries = src.pick(library)
    cfg = load_config()
    client, _ = open_write_session(execute and not fake)

    def merge_plan(groups) -> list:
        plan = []
        for _, members in groups:
            master = pick_master(members)
            others = [e for e in members if e is not master]
            plan += plan_merge(master, others, library[1])
        return plan

    def delete_plan(groups) -> list:
        return [c for _, members in groups for c in plan_delete(members)]

    pdf_of = (
        (lambda m: first_pdf(cfg, library[1], m.key))
        if what == "entries"
        else (lambda m: attachment_pdf(cfg, m))
    )

    def pdf_peek(groups) -> str:
        lines = []
        for _, members in groups:
            for member in members:
                path = pdf_of(member)
                lines.append(f"  {member.key}: {path or 'no PDF'}")
                if path:
                    thumbnail(path)
        return "\n".join(lines)

    def open_peek(groups) -> str:
        _, members = groups[0]
        master = pick_master(members)
        path = pdf_of(master)
        if path:
            open_pdf(path)
        return str(path) if path else f"{master.key}: no PDF"

    def group_cell(row) -> list[str]:
        key, members = row
        master = pick_master(members)
        label = (
            (lambda m: m.title[:28])
            if what == "entries"
            else (lambda m: m.filename[:28])
        )
        return [
            f"{key[0]}: {key[1]}"[:40],
            str(len(members)),
            " / ".join(
                ("⏺ " if m is master else "") + label(m) for m in members
            ),
        ]

    actions = [Action("m", "[m]erge", plan=merge_plan)] if what == "entries" else []
    actions += [
        Action("d", "[d]elete dups", plan=delete_plan),
        Action("v", "[v]iew pdf", peek=pdf_peek),
        Action("o", "[o]pen", peek=open_peek),
    ]

    session = Session(
        title="duplicate groups",
        rows=list(find_groups(entries, src.key_of).items()),
        headers=["matched by", "dups", "members"],
        cell=group_cell,
        actions=actions,
        execute=execute and not fake,
        do=reporter(client, cfg, execute and not fake),
        log=[],
    )
    if session.rows:
        run(session)
    mode = "EXECUTED" if session.execute else "DRY RUN"
    console.print(f"\n[bold]{mode}[/bold] – {len(session.log)} command(s)")


@app.command()
def free(
    author: str = typer.Option("", "--author", help="creator name substring"),
    tag: str = typer.Option("", "--tag", help="tag substring"),
    title: str = typer.Option("", "--title", help="title substring"),
    execute: bool = typer.Option(
        False, "--execute", help="remove matched local copies"
    ),
):
    """Free local copies of matching items – entries stay, flies live on WebDAV."""
    if not (author or tag or title):
        console.print("give at least one of --author, --tag, --title")
        raise typer.Exit()

    items, attachments = load_library()
    children: dict[str, list] = {}
    for att in attachments:
        children.setdefault(att.parent_key, []).append(att)
    cfg = load_config()
    matches = [
        it
        for it in items
        if is_match(it, author, tag, title)
        and any((cfg.storage_root / a.key).exists() for a in children.get(it.key, []))
    ]
    console.print(f"{len(matches)} matched item(s)")

    sizes: dict[str, int] = {}

    def item_cell(it) -> list[str]:
        if it.key not in sizes:
            sizes[it.key] = sum(
                dir_size(cfg.storage_root / a.key) for a in children.get(it.key, [])
            )
        return [
            it.key,
            it.title[:45],
            ", ".join(it.creators[:2])[:28] or "—",
            str(it.year or "—"),
            (it.publisher or "—")[:28],
            f"{sizes[it.key] / 1e6:.1f} MB",
        ]

    def free_plan(selection) -> list:
        return plan_free(selection, children, cfg.storage_root)

    session = Session(
        title="matched items",
        rows=matches,
        headers=["key", "title", "creator", "year", "publisher", "local"],
        cell=item_cell,
        actions=[Action("f", "[f]ree", plan=free_plan)],
        execute=execute,
        do=reporter(None, cfg, execute),
        log=[],
    )
    if session.rows:
        run(session)
    mode = "EXECUTED" if session.execute else "DRY RUN"
    console.print(f"\n[bold]{mode}[/bold] – {len(session.log)} command(s)")


@app.command()
def clean(
    what: str = typer.Option("title", "--what", help="title or names"),
    execute: bool = typer.Option(False, "--execute", help="write fixes to Zotero"),
):
    """Clean up titles or creator names in Zotero (dry run unless --execute)"""
    items, _ = load_library()
    cfg = load_config()
    client, _ = open_write_session(execute)

    rows, fix_plan, proposal_cell, headers = (
        title_rows if what == "title" else names_rows
    )(items)

    session = Session(
        title="cleanup proposals",
        rows=rows,
        headers=headers,
        cell=proposal_cell,
        actions=[Action("f", "[f]ix", plan=fix_plan)],
        execute=execute,
        do=reporter(client, cfg, execute),
        log=[],
    )

    if session.rows:
        run(session)
    mode = "EXECUTED" if session.execute else "DRY RUN"
    console.print(f"\n[bold]{mode}[/bold] – {len(session.log)} command(s)")


if __name__ == "__main__":
    app()
