import typer
from rich.console import Console
from rich.table import Table

from execute import dir_size
from grouping import attachment_key, entry_key

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


def paint(table: Table) -> None:
    console.clear()
    console.print(table)


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
        paint(table)
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
