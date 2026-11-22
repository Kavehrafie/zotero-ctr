import re
from collections import defaultdict

from difflib import SequenceMatcher

import typer
from rich.console import Console
from rich.table import Table

from fetch import load_library
from models import Attachment, Creator, Item


FUZZY_THRESHOLD = 0.85

app = typer.Typer()
console = Console()


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
        item_type="book",
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="D8",
        title="Weaving the Nation",
        year=2017,
        item_type="journalArticle",
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
    Item(
        key="M4",
        title="Desert Solitaire",
        year=1968,
        creator=Creator(first="Edward", last="Abbey")
    ),
    Item(
        key="N2",
        title="Desert Solitaire",
        creator=Creator(first="Edward", last="Abbey")
    ),
    Item(
        key="K8",
        title="",
        creator=Creator(first="Anon", last="Ymous")
    ),
    Item(
        key="P3",
        title="Dye Gardens of Oaxaka",
        year=2020,
        creator=Creator(first="Luca", last="Moretti"),
    ),
    Item(
        key="Q5",
        title="The Loom and the Loomed: Collected Essays",
        year=2021,
        creator=Creator(first="Sara", last="Kwon"),
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
    t = title.split(":")[0].strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    return "".join(ch for ch in t if ch.isalnum())


def entry_key(item: Item) -> tuple | None:
    if item.doi:
        return "doi", item.doi.lower()
    if title := normalize(item.title):
        return "title+year", title, item.year
    return None


def attachment_key(att: Attachment) -> tuple[str, str]:
    return "md5", att.md5


def fuzzy_merged(groups):
    candidates = [k for k in groups if len(k) == 3 and k[2] is not None]
    parent = {k: k for k in candidates}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, k1 in enumerate(candidates):
        for k2 in candidates[i + 1:]:
            if k1[2] != k2[2]:
                continue
            sm = SequenceMatcher(a=k1[1], b=k2[1])
            if sm.quick_ratio() >= FUZZY_THRESHOLD and sm.ratio() >= FUZZY_THRESHOLD:
                parent[find(k2)] = find(k1)
    out = {k: v for k, v in groups.items() if k not in parent}
    clusters = defaultdict(list)
    for k in candidates:
        clusters[find(k)].append(k)
    for keys in clusters.values():
        if len(keys) > 1:
            out[("fuzzy", keys[0][1], keys[0][2])] = [
                m for k in keys for m in groups[k]
            ]
        else:
            out[keys[0]] = groups[keys[0]]

    return out

def dups_only(groups):
    return {k: v for k, v in groups.items()  if len(v) > 1}

def wildcard_merged(groups):
    per_title = defaultdict(dict)
    out = {}
    for key, numbers in groups.items():
        if len(key) == 2:  # doi, md5 — already exact
            out[key] = numbers
        else:
            per_title[key[1]][key[2]] = numbers
    for title, years in per_title.items():
        if None in years:
            out[("title", title)] = [m for ms in years.values() for m in ms]
        else:
            for year, members in years.items():
                out[("title+year", title, year)] = members 
    return out



def find_groups(entries, key_of):
    groups = defaultdict(list)
    for entry in entries:
        if key := key_of(entry):
            groups[key].append(entry)
    return dups_only(fuzzy_merged(wildcard_merged(groups)))



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
    refresh: bool = typer.Option(
        False, "--refresh", help="re-fetch from Zotero, ignoring the cache"
    ),
):
    """Interactively review duplicate groups (dry run – nothing is changed)"""
    library = (ITEMS, ATTACHMENTS) if fake else load_library(refresh)
    key_of, columns, options, pick = SOURCES[what]
    entries = pick(library)

    planned = []
    groups = find_groups(entries, key_of)
    for i, (key, members) in enumerate(groups.items(), 1):
        master = pick_master(members)
        console.print(
            show(
                f"Group {i}/{len(groups)} matched by {key[0]}: {key[1]}",
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
        elif choice == "a":
            break
        elif choice == "q":
            break
    console.print(
        f"\n[bold]DRY RUN[/bold] – nothing changed. {len(planned)} planned action(s):"
    )
    for action in planned:
        console.print(f"  → {action}")



if __name__ == "__main__":
    app()