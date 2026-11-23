import shutil
from pathlib import Path

from config import Config
from models import Attachment
from remote import attachment_uploaded


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.glob("*") if f.is_file())


def free_local(cfg: Config, att: Attachment, execute: bool = False) -> tuple[str, int]:
    path = cfg.storage_root / att.key
    if not path.exists():
        return "nothing local", 0
    if execute and not attachment_uploaded(
        cfg.webdav_url, cfg.webdav_username, cfg.webdav_password, att.key
    ):
        return "kept (not on WebDAV)", 0
    size = dir_size(path)
    if execute:
        shutil.rmtree(path)
        return f"freed {att.filename}", size
    return f"{size / 1e6:.1f} MB local", size


def trash_and_free(cfg: Config, z, att: Attachment) -> str:
    z.update_item({"key": att.key, "version": att.version}, {"deleted": 1})
    if not attachment_uploaded(
        cfg.webdav_url, cfg.webdav_username, cfg.webdav_password, att.key
    ):
        return f"{att.key} kept on disk (not on WebDAV)"
    shutil.rmtree(cfg.storage_root / att.key)
    return f"{att.key} trashed, freed {att.filename}"
