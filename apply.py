import shutil

from pyzotero.errors import LocalAPIKeyRequiredError, PyZoteroError

from config import CONFIG_PATH, load_config, save_config
from fetch import zotero_client
from normalize import split_creators
from plan import FreeLocal, SplitCreators, Trash, Write
from remote import attachment_uploaded
from ui import console


class WriteFailed(RuntimeError):
    """A Zotero write returned a non-2xx status."""


def grant(z, cfg):
    granted = z.authorize_local("zotero-ctr")
    if not granted["remember"]:
        console.print(
            "[yellow]Zotero granted a ONE-TIME key – click 'Always Allow'"
            " in the dialog to stop re-authorizing on every write[/yellow]"
        )
    return cfg.model_copy(update={"local_api_key": granted["key"]})


def open_write_session(execute: bool):
    """A (client, cfg) pair for writes; (None, None) means dry run."""
    if not execute:
        return None, None
    cfg = load_config()
    z = zotero_client(cfg.local_api_key)
    if not cfg.local_api_key:
        cfg = grant(z, cfg)
        save_config(CONFIG_PATH, cfg)
    return z, cfg


def _put(z, key: str, changes: dict) -> None:
    version = z.item(key)["data"]["version"]
    z.update_item({"key": key, "version": version, **changes})


def write_item(z, key: str, changes: dict, cfg) -> None:
    """Update one item from its LIVE version; re-authorize once, raise on rejection"""
    try:
        _put(z, key, changes)
    except LocalAPIKeyRequiredError:
        save_config(CONFIG_PATH, grant(z, cfg))
        _put(z, key, changes)
    except PyZoteroError as err:
        raise WriteFailed(f"{key}: {err}") from err


def apply(command, z, cfg) -> str:
    """Run one planned command against the world; return a report line."""
    if isinstance(command, Write):
        write_item(z, command.key, command.changes, cfg)
        return f"wrote {command.key}: {', '.join(sorted(command.changes))}"
    if isinstance(command, Trash):
        write_item(z, command.key, {"deleted": 1}, cfg)
        return f"trashed {command.key}"
    if isinstance(command, SplitCreators):
        live = z.item(command.key)["data"]["creators"]
        write_item(z, command.key, {"creators": split_creators(live)}, cfg)
        return f"split creators {command.key}"
    if isinstance(command, FreeLocal):
        uploaded = attachment_uploaded(
            cfg.webdav_url, cfg.webdav_username, cfg.webdav_password, command.key
        )
        if not uploaded:
            return f"{command.key} kept on disk (not on WebDAV)"
        shutil.rmtree(cfg.storage_root / command.key)
        return f"freed {command.key} ({command.size / 1e6:.1f} MB)"
    raise TypeError(f"unknown command: {command!r}")
