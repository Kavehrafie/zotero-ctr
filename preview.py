import shutil
import subprocess
from pathlib import Path

from config import Config
from models import Attachment


def first_pdf(cfg: Config, attachments: list[Attachment], item_key: str) -> Path | None:
    pdfs = [
        a
        for a in attachments
        if a.parent_key == item_key and a.filename.lower().endswith(".pdf")
    ]
    if not pdfs:
        return None
    first = min(pdfs, key=lambda a: a.key)
    path = cfg.storage_root / first.key / first.filename
    return path if path.exists() else None


def thumbnail(path: Path) -> None:
    if not shutil.which("timg"):
        print("(timg not installed – sudo dnf install timg)")
        return
    subprocess.run(["timg", str(path)], check=False)


def open_pdf(path: Path) -> None:
    subprocess.run(["xdg-open", str(path)], check=False)
