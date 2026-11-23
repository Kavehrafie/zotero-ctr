import typer
from pyzotero.errors import LocalAPIKeyRequiredError

from grouping import find_groups
from normalize import clean_title, split_creators
from config import CONFIG_PATH, load_config, save_config
from execute import free_local, trash_and_free
from fetch import load_library, zotero_client
from fixtures import ATTACHMENTS, ITEMS
from merge import merge_group
from preview import first_pdf, open_pdf, thumbnail
from ui import SOURCES, browse, choose, console, decide, paint, proposal_table


app = typer.Typer()


def grant(client, cfg):
    granted = client.authorize_local("zotero-ctr")
    if not granted["remember"]:
        console.print(
            "[yellow]Zotero granted a ONE-TIME key — click 'Always Allow' "
            "in the dialog to stop re-authorizing on every write[/yellow]"
        )
    return cfg.model_copy(update={"local_api_key": granted["key"]})

def open_write_session(execute: bool):
    if not execute:
        return None, None, None
    cfg = load_config()
    client = zotero_client(cfg.local_api_key)
    if not cfg.local_api_key:
        cfg = grant(client, cfg)
        save_config(CONFIG_PATH, cfg)

    def write(action):
        nonlocal cfg
        try:
            return action()
        except LocalAPIKeyRequiredError:
            cfg = grant(client, cfg)
            save_config(CONFIG_PATH, cfg)
            return action()

    return client, cfg, write

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
    key_of, columns, options, pick = SOURCES[what]
    entries = pick(library)
    cfg = load_config()
    client, _, write = open_write_session(execute)

    planned = []
    items = list(find_groups(entries, key_of).items())

    def resolve(i) -> str:
        """Decide one group and act on it: done / skip / quit."""
        key, members = items[i]
        choice, master = decide(columns, options, key, members)
        others = [e for e in members if e is not master]
        if choice == "m":
            if client and write:
                console.print(
                    f"  {write(lambda: merge_group(client, master, others, library[1]))}"
                )
            else:
                planned.append(
                    f"merge {', '.join(e.key for e in others)} into {master.key}"
                )
        elif choice == "d":
            if client and write:
                for att in others:
                    console.print(f"  {write(lambda: trash_and_free(cfg, client, att))}")
            else:
                planned.append(
                    f"delete {', '.join(e.key for e in others)} (keep {master.key})"
                )
        elif choice == "p":
            for member in members:
                path = first_pdf(cfg, library[1], member.key)
                console.print(f"  {member.key}: {path or 'no PDF'}")
                if path:
                    thumbnail(path)
        elif choice == "o":
            path = first_pdf(cfg, library[1], master.key)
            if path:
                open_pdf(path)
            console.print(f"  opened {path}" if path else f"  {master.key}: no PDF")
        if choice in ("a", "q"):
            return "quit"
        return "done" if choice in ("m", "d") else "skip"

    if items:
        browse(items, resolve)
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
    if execute and not typer.confirm(f"remove local copies for {len(chosen)} item(s)?"):
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

@app.command()
def clean(
    what: str = typer.Option("title", "--what", help="title or names"),
    execute: bool = typer.Option(False, "--execute", help="write fixes to Zotero"),
):
    """Clean up titles or creator names in Zotero (dry run unless --execute)"""
    items, _ = load_library() 
    client, cfg, write = open_write_session(execute)

    if what == "title":
        proposals =[
            (it, {"title": clean_title(it.title)}) for it in items if clean_title(it.title) != it.title
        ]
    else:
        proposals = [(it, None) for it in items if any(", " in c for c in it.creators)]

    planned, written = [], 0
    for i, (it, ch) in enumerate(proposals, 1):
        paint(proposal_table(i, len(proposals), it, ch))
        if typer.prompt("[y] fix [n] skip [q] quit", default="y").lower() != "y":
            continue
        if client and write:
            if what == "title":
                write(
                    lambda it=it, ch=ch: client.update_item(
                        {"key": it.key, "version": it.version}, ch
                    )
                )
            else:
                live = client.item(it.key)["data"]["creators"]
                write(
                    lambda it=it, f=split_creators(live): client.update_item(
                        {"key": it.key, "version": it.version}, {"creators": f}
                    )
                )
            written += 1
        else:
            planned.append(f"{it.key}: {ch or 'split creators'}")
    mode = "EXECUTED" if client else "DRY RUN"
    console.print(f"\n[bold]{mode}[/bold] – {written} written, {len(planned)} planned action(s)")
            

if __name__ == "__main__":
    app()
