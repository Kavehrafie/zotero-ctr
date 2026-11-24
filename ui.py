from typing import Callable, NamedTuple

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.selection import Selection
from textual.widgets import DataTable, Footer, Header, SelectionList

import typer
from rich.console import Console
from rich.table import Table

from grouping import attachment_key, entry_key, pick_master
from plan import describe

console = Console()

PAGE_SIZE = 9


def paint(table: Table) -> None:
    console.clear()
    console.print(table)


def indices(choice: str, n: int) -> list[int]:
    """Parse page numbers like 1,3-5 into zero-base indices."""
    out = []
    for token in choice.split(","):
        lo, _, hi = token.partition("-")
        first, last = int(lo), int(hi or lo)
        if not 1 <= first <= last <= n:
            raise IndexError
        out.extend(range(first - 1, last))
    return out


class Source(NamedTuple):
    key_of: Callable
    pick: Callable


SOURCES = {
    "entries": Source(entry_key, lambda lib: lib[0]),
    "attachments": Source(attachment_key, lambda lib: lib[1]),
}


class CtrApp(App):
    CSS = """
    #panes {height: 1fr;}
    #rows {width: 2fr;}
    #members {width: 1fr;}
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, session):
        self.session = session
        self.selected: set[int] = set()
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panes"):
            yield DataTable(cursor_type="row", id="rows")
            yield SelectionList(id="members")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rows", DataTable)
        table.add_column("sel", *self.session.headers)
        for row in self.session.rows:
            table.add_row("", *self.session.headers)
        if not self.session.members:
            self.query_one("#members", SelectionList).display = False

    def on_data_table_row_highlighted(self, event) -> None:
        if not self.session.members:
            return
        pane = self.query_one("#members", SelectionList)
        pane.clear_options()
        group = self.session.rows[event.cursor_row]
        keeper = pick_master(self.session.members(group))
        for m in self.session.members(group):
            label = f"{' ✼' if m is keeper else ''} {m.key} {getattr(m, 'title', None) or m.filename[:40]}"
            pane.add_option(Selection(label, m, is_selected=False))

    def on_key(self, event) -> None:
        if event.character == " ":
            self.toggle_cursor_row()
            return


class Action(NamedTuple):
    key: str
    label: str
    plan: Callable | None = None
    peek: Callable | None = None


class Session(NamedTuple):
    """What a command contributes: configuration, not state."""

    title: str
    rows: list
    headers: list
    cell: Callable
    actions: list[Action]
    execute: bool
    do: Callable
    log: list


class Ctx:
    """What the engine accumulates while running"""

    def __init__(self, session: Session):
        self.session = session
        self.chosen: list = []
        self.action: Action | None = None
        self.plan: list = []
        self.lines: list = []


def browse(c: Ctx):
    """Paint, select, page; an action key is the transition out."""
    s = c.session
    chosen: set[int] = set()
    page = 0
    pages = max(1, -(-len(s.rows) // PAGE_SIZE))
    while True:
        view = s.rows[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        table = Table(
            title=f"{s.title} – {len(chosen)}/{len(s.rows)} selected, page {page + 1}/{pages}"
        )
        table.add_column("#")
        table.add_column("sel")
        for header in s.headers:
            table.add_column(header)
        for n, row in enumerate(view, 1):
            table.add_row(
                str(n), "*" if page * PAGE_SIZE + n - 1 in chosen else "", *s.cell(row)
            )
        paint(table)
        labels = " ".join(a.label for a in s.actions)
        choice = typer.prompt(
            f"[#] toggle 1, 3-5 [a]ll [c]lear [n]ext [p]rev {labels} [q]uit"
        ).lower()
        if choice == "q":
            return None
        if choice == "n":
            page = min(page + 1, pages - 1)
        elif choice == "p":
            page = max(page - 1, 0)
        elif choice == "a":
            chosen.update(range(len(s.rows)))
        elif choice == "c":
            chosen.clear()
        else:
            try:
                for r in indices(choice, len(view)):
                    chosen.symmetric_difference_update({page * PAGE_SIZE + r})
                continue

            except (ValueError, IndexError):
                pass
            action = next((a for a in s.actions if a.key == choice), None)
            if not action:
                console.print("[red]?[/red]")
            elif not chosen:
                console.print("[yellow]select rows first[/yellow]")
            elif action.peek:
                console.print(action.peek([s.rows[i] for i in sorted(chosen)]))
                typer.prompt("press [enter] to go back", default="")
            else:
                c.chosen = [s.rows[i] for i in sorted(chosen)]
                c.action = action
                return "plan"


def plan_state(c: Ctx):
    c.plan = c.action.plan(c.chosen)
    return "confirm" if c.session.execute else "report"


def confirm(c: Ctx):
    for cmd in c.plan:
        console.print(f"  {describe(cmd)}")
    return "apply" if typer.confirm(f"apply {len(c.plan)} command(s)?") else "browse"


def apply_state(c: Ctx):
    c.lines = [c.session.do(cmd) for cmd in c.plan]
    spent = {id(row) for row in c.chosen}
    c.session = c.session._replace(
        rows=[row for row in c.session.rows if id(row) not in spent]
    )
    return "report"


def report(c: Ctx):
    lines = c.lines if c.session.execute else [describe(cmd) for cmd in c.plan]
    for line in lines:
        console.print(f"  {line}")
    c.session.log.extend(lines)
    return "browse"


STATES = {
    "browse": browse,
    "plan": plan_state,
    "confirm": confirm,
    "apply": apply_state,
    "report": report,
}


def run(session: Session) -> None:
    """States are functions; the return value is the transition."""
    c = Ctx(session)
    state = "browse"
    while state:
        state = STATES[state](c)
