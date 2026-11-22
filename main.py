from collections import defaultdict

import typer
from rich.console import Console
from rich.table import Table

from fetch import load_library
from models import Attachment, Creator, Item

app = typer.Typer()
console = Console()


ENTRY_COLUMNS = [
    ("title", lambda it: it.title or "—"),
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


ITEMS = [
    Item(
        key="A1",
        title="Textile Histories",
        year=2019,
        doi="10.2307/25154106",
        creator=Creator(first="Maya", last="Calder"),
    ),
    Item(
        key="B7",
        title="Textile Histories",
        year=2019,
        doi="10.2307/25154106",
        creator=Creator(first="Maya", last="Calder"),
    ),
    Item(
        key="C3",
        title="Weaving the Nation",
        year=2017,
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="D8",
        title="Weaving the Nation",
        year=2017,
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="E2",
        title="weaving the nation!",
        year=2017,
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="F4",
        title="The Loom and the Loomed",
        year=2021,
        doi="10.1080/00223344",
        creator=Creator(first="Sara", last="Kwon"),
    ),
    Item(
        key="G9",
        title="Dye Gardens of Oaxaca",
        year=2020,
        creator=Creator(first="Luca", last="Moretti"),
    ),
    Item(
        key="H5",
        title="Pigment and Empire",
        year=2015,
        doi="10.1017/s00104175",
        creator=Creator(first="Nora", last="Feld"),
    ),
    Item(
        key="J6",
        title="Pigment and Empire",
        year=2015,
        doi="10.1017/s00104175",
        creator=Creator(first="Nora", last="Feld"),
    ),
]

ATTACHMENTS = [
    Attachment(key="X1", filename="textile-histories.pdf", md5="aa11", parent_key="A1"),
    Attachment(
        key="X2", filename="textile-histories (1).pdf", md5="aa11", parent_key="B7"
    ),
    Attachment(key="X3", filename="loom.pdf", md5="bb22", parent_key="F4"),
    Attachment(key="X4", filename="loom copy.pdf", md5="bb22", parent_key="F4"),
    Attachment(key="X5", filename="dye-gardens.pdf", md5="cc33", parent_key="G9"),
]


def normalize(title: str) -> str:
    return "".join(ch for ch in title.lower() if ch.isalnum())


def entry_key(item: Item) -> tuple[str, str]:
    if item.doi:
        return "doi", item.doi.lower()
    return "title+year", f"{normalize(item.title)} {item.year}"


def attachment_key(att: Attachment) -> tuple[str, str]:
    return "md5", att.md5


def find_groups(entries, key_of):
    groups = defaultdict(list)
    for entry in entries:
        groups[key_of(entry)].append(entry)
    return {label: members for label, members in groups.items() if len(members) > 1}


def pick_master(members):
    return min(members, key=lambda e: e.key)


def show(title: str, members, master, columns) -> Table:
    table = Table(title=title)
    table.add_column("")  # key + marker
    for header, _ in columns:
        table.add_column(header)
    for entry in members:
        marker = "⏺ " if entry is master else "  "
        cells = [cell(entry) for _, cell in columns]
        table.add_row(f"{marker}{entry.key}", *cells)
    return table


SOURCES = {
    "entries": (
        entry_key,
        ENTRY_COLUMNS,
        "[m]erge [d]elete dups [s]kip [a]ll skip [q]uit",
        lambda lib: lib[0],
    ),
    "attachments": (
        attachment_key,
        ATTACHMENT_COLUMNS,
        "[d]elete dups [s]kip [a]ll skip [q]uit",
        lambda lib: lib[1],
    ),
}


@app.command()
def review(
    what: str = typer.Option("entries", "--what", help="entries or attachments"),
    fake: bool = typer.Option(
        False, "--fake", help="use mockup data instead of Zotero"
    ),
):
    """Interactively review duplicate groups (dry run – nothing is changed)"""
    library = (ITEMS, ATTACHMENTS) if fake else load_library()
    key_of, columns, options, pick = SOURCES[what]
    entries = pick(library)

    planned = []
    groups = find_groups(entries, key_of)
    for i, ((method, value), members) in enumerate(groups.items(), 1):
        master = pick_master(members)
        console.print(
            show(
                f"Group {i}/{len(groups)} matched by {method}: {value}",
                members,
                master,
                columns,
            )
        )
        choice = typer.prompt(options, default="s").lower()
        others = [e.key for e in members if e is not master]
        if choice == "m":
            planned.append(f"merge {', '.join(others)} into {master.key}")
        elif choice == "d":
            planned.append(f"delete {', '.join(others)} (keep {master.key})")
        elif choice == "q":
            break
    console.print(
        f"\n[bold]DRY RUN[/bold] – nothing changed. {len(planned)} planned action(s):"
    )
    for action in planned:
        console.print(f"  → {action}")


if __name__ == "__main__":
    app()
