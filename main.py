import typer
from pyzotero.errors import LocalAPIKeyRequiredError
from rich.console import Console
from rich.table import Table

from config import CONFIG_PATH, load_config, save_config
from execute import dir_size, free_local, trash_and_free
from fetch import load_library, zotero_client
from fixtures import ATTACHMENTS, ITEMS
from grouping import attachment_key, entry_key, find_groups, pick_master
from merge import merge_group
from preview import first_pdf, open_pdf, thumbnail

app = typer.Typer()
console = Console()


PAGE_SIZE = 9
ENTRY_COLUMNS = [
    ("title", lambda it: it.title or "—"),
    ("type", lambda it: it.item_type or "—"),
    ("year", lambda it: str(it.year or "—")),
    (
        "creator",
        lambda it: " ".join(filter(None, [it.creator.first, it.creator.last])) or "—",
    ),
    ("doi", lambda it: it.doi or "—"),
]

ATTACHMENT_COLUMNS = [
    ("file", lambda a: a.filename),
    ("parent item", lambda a: a.parent_key),
]


def show(title: str, members, master, columns) -> Table:
    table = Table(title=title)
    table.add_column("#")  # key + marker
    for header, _ in columns:
        table.add_column(header)
    for n, entry in enumerate(members, 1):
        marker = "⏺ " if entry is master else "  "
        cells = [cell(entry) for _, cell in columns]
        table.add_row(f"{n} {marker}{entry.key}", *cells)
    return table


SOURCES = {
    "entries": (
        entry_key,
        ENTRY_COLUMNS,
        "[m]erge [d]elete dups [1-9] keep [p]df [o]pen [s]kip [a]ll skip [q]uit",
        lambda lib: lib[0],
    ),
    "attachments": (
        attachment_key,
        ATTACHMENT_COLUMNS,
        "[d]elete dups [1-9] keep [s]kip [a]ll skip [q]uit",
        lambda lib: lib[1],
    ),
}


def grant(client, cfg):
    granted = client.authorize_local("zotero-ctr")
    if not granted["remember"]:
        console.print(
            "[yellow]Zotero granted a ONE-TIME key — click 'Always Allow' "
            "in the dialog to stop re-authorizing on every write[/yellow]"
        )
    return cfg.model_copy(update={"local_api_key": granted["key"]})


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
    """Interactively review duplicate groups (dry run unless --execute)"""
    library = (ITEMS, ATTACHMENTS) if fake else load_library(refresh)
    key_of, columns, options, pick = SOURCES[what]
    entries = pick(library)

    client, cfg = None, None
    if execute:
        cfg = load_config()
        client = zotero_client(cfg.local_api_key)
        if not cfg.local_api_key:
            cfg = grant(client, cfg)
            save_config(CONFIG_PATH, cfg)

    def write(action):
        """Run one write; on an expired key, re-authorize once and retry."""
        nonlocal cfg
        if client is None or cfg is None:
            raise RuntimeError("write() needs the --execute handshake to have run")
        try:
            return action()
        except LocalAPIKeyRequiredError:
            cfg = grant(client, cfg)
            save_config(CONFIG_PATH, cfg)
            return action()

    planned = []
    groups = find_groups(entries, key_of)
    for i, (key, members) in enumerate(groups.items(), 1):
        master = pick_master(members)
        header = f"Group {i}/{len(groups)} matched by {key[0]}: {key[1]}"
        console.print(show(header, members, master, columns))
        choice = typer.prompt(options, default="s").lower()
        if choice.isdigit() and 1 <= int(choice) <= len(members):
            master = members[int(choice) - 1]
            console.print(show(header, members, master, columns))
            choice = typer.prompt(options, default="s").lower()
        others = [e for e in members if e is not master]
        if choice == "m":
            if client:
                result = write(
                    lambda master=master, others=others: merge_group(
                        client, master, others, library[1]
                    )
                )
                console.print(f"  {result}")
            else:
                planned.append(
                    f"merge {', '.join(e.key for e in others)} into {master.key}"
                )
        elif choice == "p":
            cfg = cfg or load_config()
            for member in members:
                path = first_pdf(cfg, library[1], member.key)
                console.print(f"  {member.key}: {path or 'no PDF'}")
                if path:
                    thumbnail(path)
        elif choice == "o":
            cfg = cfg or load_config()
            path = first_pdf(cfg, library[1], master.key)
            if path:
                open_pdf(path)
                console.print(f"  opened {path}")
            else:
                console.print(f"  {master.key}: no PDF")
        elif choice == "d":
            if client and cfg:
                for att in others:
                    result = write(
                        lambda cfg=cfg, att=att: trash_and_free(cfg, client, att)
                    )
                    console.print(f"  {result}")
            else:
                planned.append(
                    f"delete {', '.join(e.key for e in others)} (keep {master.key})"
                )
        elif choice in ("a", "q"):
            break
    mode = "EXECUTED" if client else "DRY RUN"
    console.print(f"\n[bold]{mode}[/bold] – {len(planned)} planned action(s):")
    for action in planned:
        console.print(f"  → {action}")


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
        if (
            (author and any(author.lower() in c.lower() for c in it.creators))
            or (tag and tag.lower() in (t.lower() for t in it.tags))
            or (title and title.lower() in it.title.lower())
        )
        and any((cfg.storage_root / a.key).exists() for a in children.get(it.key, []))
    ]
    console.print(f"{len(matches)} matched item(s)")

    chosen = choose(cfg, children, matches)
    if not chosen:
        console.print("nothing selected")
        raise typer.Exit()
    if execute and not typer.confirm(
        f"remove local copies for {len(chosen)} item(s)?"
    ):
        raise typer.Exit()

    freed = 0
    for it in chosen:
        console.print(f"{it.key} {it.title[:60]}")
        for att in children.get(it.key, []):
            status, size = free_local(cfg, att, execute)
            freed += size
            console.print(f"  {att.key} {status}")
    label = "freed" if execute else "would free"
    console.print(f"\n[bold]{label}: {freed / 1e6:.1f} MB[/bold]")


def choose(cfg, children, matches) -> list:
    selected: set[str] = set()
    page = 0
    pages = max(1, -(-len(matches) // PAGE_SIZE))
    options = "[#] toggle 1,3-5 [a]ll [c]lear [n]ext [p]rev [f]ree [q]uit"
    while True:
        rows = matches[page * PAGE_SIZE : page * PAGE_SIZE + PAGE_SIZE]
        table = Table(
            title=f"{len(selected)}/{len(matches)} selected — page {page + 1}/{pages}"
        )
        table.add_column("#")
        table.add_column("sel")
        table.add_column("key")
        table.add_column("title")
        table.add_column("creator")
        table.add_column("year")
        table.add_column("publisher")
        table.add_column("local")
        for n, it in enumerate(rows, 1):
            kids = children.get(it.key, [])
            size = sum(dir_size(cfg.storage_root / a.key) for a in kids)
            mark = "" if it.key in selected else ""
            table.add_row(
                str(n),
                mark,
                it.key,
                it.title[:45],
                ", ".join(it.creators[:2])[:28] or "—",
                str(it.year or "—"),
                (it.publisher or "—")[:28],
                f"{size / 1e6:.1f} MB",
            )
        console.print(table)
        choice = typer.prompt(options).lower()
        if choice == "n":
            page = min(page + 1, pages - 1)
        elif choice == "p":
            page = max(page - 1, 0)
        elif choice == "a":
            selected.update(it.key for it in matches)
        elif choice == "c":
            selected.clear()
        elif choice == "f":
            return [it for it in matches if it.key in selected]
        elif choice == "q":
            raise typer.Exit()
        else:
            try:
                for token in choice.split(","):
                    lo, _, hi = token.partition("-")
                    first, last = int(lo), int(hi or lo)
                    if not 1 <= first <= last <= len(rows):
                        raise IndexError
                    for r in range(first - 1, last):
                        selected.symmetric_difference_update({rows[r].key})
            except (ValueError, IndexError):
                console.print("[red]?[/red]")


if __name__ == "__main__":
    app()
