import shutil

from config import Config
from models import Attachment
from remote import attachment_uploaded


def trash_and_free(cfg: Config, z, att: Attachment) -> str:
    z.update_item({"key": att.key, "version": att.version}, {"deleted": 1})
    if not attachment_uploaded(
        cfg.webdav_url, cfg.webdav_username, cfg.webdav_password, att.key
    ):
        return f"{att.key} kept on disk (not on WebDAV)"
    shutil.rmtree(cfg.storage_root / att.key)
    return f"{att.key} trashed, freed {att.filename}"
