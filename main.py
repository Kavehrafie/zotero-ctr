import typer
from pyzotero.errors import LocalAPIKeyRequiredError

from config import CONFIG_PATH, load_config, save_config
from execute import free_local, trash_and_free
from fetch import load_library, zotero_client
from fixtures import ATTACHMENTS, ITEMS
from grouping import find_groups, pick_master
from merge import merge_group
from preview import first_pdf, open_pdf, thumbnail
from ui import SOURCES, choose, console, paint, show

app = typer.Typer()


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
        paint(show(header, members, master, columns))
        choice = typer.prompt(options, default="s").lower()
        if choice.isdigit() and 1 <= int(choice) <= len(members):
            master = members[int(choice) - 1]
            paint(show(header, members, master, columns))
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


if __name__ == "__main__":
    app()
