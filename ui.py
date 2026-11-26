import tomllib
from pathlib import Path
from typing import Callable, NamedTuple

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Static
from textual_image.widget import AutoImage

from grouping import attachment_key, entry_key
from icons import file_icon
from plan import FILLABLE, describe

VERSION = tomllib.loads(
    (Path(__file__).parent / "pyproject.toml").read_text()
)["project"]["version"]


class Source(NamedTuple):
    key_of: Callable
    pick: Callable


SOURCES = {
    "entries": Source(entry_key, lambda lib: lib[0]),
    "attachments": Source(attachment_key, lambda lib: lib[1]),
}


class Action(NamedTuple):
    key: str
    label: str
    plan: Callable | None = None
    peek: Callable | None = None
    dialog: Callable | None = None
    screen: Callable | None = None


class Session(NamedTuple):
    """What a view contributes: configuration only -- state lives on the app."""

    title: str
    rows: list
    headers: list
    cell: Callable
    actions: list[Action]
    do: Callable
    widths: tuple = ()


class Panel(ModalScreen[object]):
    """Framed modal: titled panel plus a hints line; subclasses supply the body.

    border_title renders only on a widget that has a border, so the title goes
    on the panel, never on the screen. The framing lives in DEFAULT_CSS, not
    CSS: a screen's own CSS registers only when that screen mounts (as its one
    most-derived CSS var), so base-class CSS would apply only after some other
    modal had mounted first. DEFAULT_CSS is collected per MRO base at startup
    -- SCOPED_CSS=False unscopes it -- with no mount-order trap."""

    SCOPED_CSS = False
    DEFAULT_CSS = """
    Panel { align: center middle; }
    Panel #panel { width: 70%; height: 80%; border: round $accent; padding: 0 2; background: $surface; }
    Panel #hints { dock: bottom; content-align: center middle; height: 1; color: $accent; }
    """
    HINTS = ""
    panel_title = ""

    def body(self) -> ComposeResult:
        raise NotImplementedError

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="panel") as panel:
            panel.border_title = self.panel_title
            yield from self.body()
        yield Static(self.HINTS, id="hints")

    def on_mount(self) -> None:
        self.query_one("#panel", VerticalScroll).focus()


class Confirm(Panel):
    """The plan, then y or n."""

    BINDINGS = [("y", "yes", "apply"), ("n", "no", "cancel"), ("escape", "no", "cancel")]
    HINTS = "y apply · n cancel · esc cancel"

    def __init__(self, plan: list, label: str) -> None:
        self.plan = plan
        self.panel_title = f"{label} · EXECUTE · {len(plan)} command(s)"
        super().__init__()

    def body(self) -> ComposeResult:
        yield Static(Text("\n".join(f"  {describe(c)}" for c in self.plan)))

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class Report(Panel):
    BINDINGS = [("enter", "back", "back"), ("q", "back", "back")]
    HINTS = "enter back · q back"

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        failed = sum(1 for line in lines if line.startswith("✗"))
        self.panel_title = (
            f"report · {len(lines) - failed} ok · {failed} failed"
            if failed
            else f"report · {len(lines)} ok"
        )
        super().__init__()

    def body(self) -> ComposeResult:
        body = Text()
        for line in self.lines:
            body.append(line, style="red" if line.startswith("✗") else None)
            body.append("\n")
        yield Static(body)

    def action_back(self) -> None:
        self.app.pop_screen()


class MergeDialog(Panel):
    """Pick the master and each attachment's fate, then apply."""

    BINDINGS = [
        ("up", "cursor_up", "up"),
        ("down", "cursor_down", "down"),
        ("m", "master", "make master"),
        ("a", "flip", "keep/drop attachment"),
        ("y", "yes", "apply"),
        ("n", "no", "cancel"),
        ("escape", "no", "cancel"),
    ]
    HINTS = "↑/↓ move · m make master · a keep/drop att · y apply · n cancel"
    CSS = """
    MergeDialog #panel { width: 90%; height: 85%; }
    """

    def __init__(self, entries: list, attachments_of: dict, master) -> None:
        super().__init__()
        self.entries = entries
        self.panel_title = f"merge · {len(entries)} entries · pick master"
        self.master = master
        self.atts = attachments_of
        self.fates: dict[str, str] = {}
        self.build_plan: Callable | None = None
        self.pos = 0
        self.rows: list[tuple] = []
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        self.rows = [(e, None) for e in self.entries]
        for e in self.entries:
            if e is self.master:
                continue
            for a in self.atts.get(e.key, []):
                self.rows.append((e, a))
                self.fates.setdefault(a.key, "move → master")
        self.pos = min(self.pos, len(self.rows) - 1)

    def body(self) -> ComposeResult:
        yield Static(self.brief_text(), id="brief")

    def brief_text(self) -> Text:
        """The dialog body, built eagerly — compose paints it on the first frame."""
        out = []
        fills = 0
        for i, (e, a) in enumerate(self.rows):
            cur = ">" if i == self.pos else " "
            if a is None:
                tag = "MASTER" if e is self.master else "dup  "
                line = f"{cur} {tag} {e.key}  {e.title[:42]}"
                if i == self.pos:
                    line += (
                        f"\n          {e.year or '—'} · "
                        f"{e.publisher or '—'} · {e.doi or 'no DOI'}"
                    )
                out.append(line)
                if e is not self.master:
                    for attr, field in FILLABLE.items():
                        mine, theirs = getattr(self.master, attr), getattr(e, attr)
                        if theirs and theirs != mine:
                            if not mine:
                                fills += 1
                                out.append(
                                    f"        {field}: {str(theirs)[:32]} → fills master"
                                )
                            else:
                                out.append(
                                    f"        {field}: dup value dropped (master has its own)"
                                )
            else:
                out.append(
                    f"{cur}   {file_icon(a.filename, a.content_type)} {a.key}"
                    f"  {self.fates[a.key]:<24} {a.filename[:30]}"
                )
        moves = sum(1 for v in self.fates.values() if v.startswith("move"))
        out.append("")
        out.append(
            f"outcome: {fills} fill write(s) · {len(self.entries) - 1} trash"
            f" · {moves} attachment move(s)"
        )
        return Text("\n".join(out))

    def _refresh_panel(self) -> None:
        self.query_one("#brief", Static).update(self.brief_text())

    def action_cursor_up(self) -> None:
        self.pos = max(0, self.pos - 1)
        self._refresh_panel()

    def action_cursor_down(self) -> None:
        self.pos = min(len(self.rows) - 1, self.pos + 1)
        self._refresh_panel()

    def action_master(self) -> None:
        e, a = self.rows[self.pos]
        if a is None and e is not self.master:
            self.master = e
            self._rebuild_rows()
        self._refresh_panel()

    def action_flip(self) -> None:
        e, a = self.rows[self.pos]
        move, drop = "move → master", "drop (trashed with dup)"
        if a is not None:
            self.fates[a.key] = drop if self.fates[a.key].startswith("move") else move
        self._refresh_panel()

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class Evidence(Panel):
    """The selected rows' PDF pages, rendered inside the app."""

    BINDINGS = [("escape", "close", "close"), ("q", "close", "close"), ("enter", "close", "close")]
    CSS = """
    Evidence #panel { width: 90%; height: 85%; }
    Evidence #pages { height: 1fr; align: center middle; }
    Evidence Image { width: 1fr; height: 1fr; }
    """
    HINTS = "esc close"

    def __init__(self, images: list) -> None:
        self.images = images
        self.panel_title = f"evidence · {len(images)} page(s)" if images else "evidence"
        super().__init__()

    def body(self) -> ComposeResult:
        with Horizontal(id="pages"):
            if self.images:
                for img in self.images:
                    yield AutoImage(img)
            else:
                yield Static("no PDF on disk for the selection")

    def action_close(self) -> None:
        self.dismiss(None)


class CtrApp(App):
    """One table, many views. t cycles views, x toggles execute, space selects."""

    CSS = """
    #status {height: 1;}
    #rows {height: 1fr;}
    """
    BINDINGS = [
        ("space", "select", "select"),
        ("x", "execute", "toggle execute"),
        ("m", "act('m')", "merge"),
        ("d", "act('d')", "trash dups"),
        ("v", "act('v')", "evidence"),
        ("o", "act('o')", "open"),
        ("f", "act('f')", "apply"),
    ]

    def __init__(self, views: dict[str, Callable]):
        self.views = views
        self.order = list(views)
        self.current = self.order[0] if self.order else ""
        self.execute = False
        self.selected: set[int] = set()
        self.sessions: dict[str, Session] = {}
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("", id="status")
        yield DataTable(cursor_type="row", id="rows")
        yield Footer()

    @property
    def session(self) -> Session:
        return self.sessions[self.current]

    def on_mount(self) -> None:
        if self.current:
            self.show(self.current)

    def show(self, view: str) -> None:
        """Make one view current; sessions build off the UI thread."""
        if view not in self.sessions:
            self.report_status("loading…")
            self._build_session(view)
            return
        self._activate(view)

    def _activate(self, view: str) -> None:
        self.current = view
        self.selected.clear()
        table = self.query_one("#rows", DataTable)
        self.prepare(table)
        table.focus()
        self.refresh_bindings()
        self.report_status()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """The footer lists only what the current view can do."""
        if action != "act":
            return True
        if self.screen is not self.default_screen or self.current not in self.sessions:
            return None
        return True if any(a.key == parameters[0] for a in self.session.actions) else None

    @work(thread=True, exclusive=True)
    def _build_session(self, view: str) -> None:
        session = self.views[view]()

        def ready() -> None:
            self.sessions[view] = session
            self._activate(view)

        self.call_from_thread(ready)

    def report_status(self, note: str = "") -> None:
        mode = "EXECUTE" if self.execute else "DRY RUN"
        legend = " · ".join(
            f"[reverse]{i} {name}[/reverse]" if name == self.current else f"{i} {name}"
            for i, name in enumerate(self.order, 1)
        )
        if note:
            tail = note
        elif self.current in self.sessions and self.session.rows:
            tail = f"{len(self.session.rows)} rows"
        else:
            tail = f"empty — pick a mode with 1-{len(self.order)}"
        self.query_one("#status", Static).update(
            f"zotero-ctr v{VERSION} · {legend} · {mode} · {tail}"
        )

    def action_execute(self) -> None:
        if self.screen is not self.default_screen:
            return
        self.execute = not self.execute
        self.report_status()

    def prepare(self, table: DataTable) -> None:
        """Rebuild the table from the session rows."""
        table.clear(columns=True)
        widths = (3, *self.session.widths)
        columns = [
            table.add_column(label, width=w)
            for label, w in zip(("", *self.session.headers), widths)
        ]
        self.sel_column = columns[0]
        for pos, row in enumerate(self.session.rows):
            table.add_row(
                "*" if pos in self.selected else "",
                *self.session.cell(row),
                key=str(pos),
            )

    def on_key(self, event) -> None:
        if self.screen is not self.default_screen:
            return
        if event.character and event.character.isdigit():
            n = int(event.character)
            if 1 <= n <= len(self.order):
                self.show(self.order[n - 1])

    def action_select(self) -> None:
        self.toggle_cursor_row()

    def action_act(self, key: str) -> None:
        if self.screen is not self.default_screen or self.current not in self.sessions:
            self.notify("still loading…")
            return
        action = next((a for a in self.session.actions if a.key == key), None)
        if action is None:
            self.notify(f"'{key}' not available in this mode")
            return
        self.trigger(action)

    def toggle_cursor_row(self) -> None:
        table = self.query_one("#rows", DataTable)
        pos = table.cursor_row
        self.selected.symmetric_difference_update({pos})
        table.update_cell(str(pos), self.sel_column, "*" if pos in self.selected else "")

    def current_selection(self) -> list:
        return [self.session.rows[i] for i in self.selected]

    def trigger(self, action: Action) -> None:
        selection = self.current_selection()
        if not selection:
            self.notify("space-select rows first, then press the action key", severity="warning")
            return
        if action.screen:
            self.push_screen(action.screen(selection))
            return
        if action.peek:
            with self.suspend():
                try:
                    print(action.peek(selection))
                    input("\n  [enter] back to the table…")
                except Exception as err:
                    input(f"\n  peek failed: {err}\n  [enter] back…")
            return
        if action.dialog:
            dlg = action.dialog(selection)
            self.push_screen(dlg, self.dialog_ok(dlg))
            return
        plan = action.plan and action.plan(selection)
        if not plan:
            self.notify("nothing to do")
            return
        if self.execute:
            self.push_screen(Confirm(plan, action.label), self.confirm_ok(plan))
        else:
            self.apply_plan(plan)

    def confirm_ok(self, plan: list) -> Callable:
        def run(ok: bool) -> None:
            if ok:
                self.call_after_refresh(self.apply_plan, plan)

        return run

    def dialog_ok(self, dlg) -> Callable:
        def run(ok: bool) -> None:
            if ok:
                self.call_after_refresh(self.apply_plan, dlg.build_plan(dlg))

        return run

    def apply_plan(self, plan: list) -> None:
        """Dry-run reports immediately; execute writes off the UI thread."""
        if not self.execute:
            self.push_screen(Report([describe(c) for c in plan]))
            return
        self._apply(plan)

    @work(thread=True)
    def _apply(self, plan: list) -> None:
        lines = []
        for command in plan:
            try:
                lines.append(self.session.do(command))
            except Exception as err:
                lines.append(f"✗ {type(err).__name__}: {err}")
                break

        def done() -> None:
            self.consume_selection()
            failed = [line for line in lines if line.startswith("✗")]
            if failed:
                self.push_screen(Report(lines))
            self.notify(
                f"✓ {len(lines) - len(failed)} applied"
                if not failed
                else f"✗ {len(failed)} of {len(lines)} failed — details in report",
                severity="information" if not failed else "error",
            )
            self.report_status()

        self.call_from_thread(done)

    def consume_selection(self) -> None:
        rows = self.session.rows
        spent = {id(rows[i]) for i in self.selected}
        self.sessions[self.current] = self.session._replace(
            rows=[row for row in rows if id(row) not in spent]
        )
        self.selected.clear()
        self.prepare(self.query_one("#rows", DataTable))
