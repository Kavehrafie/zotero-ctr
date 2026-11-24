import os
import re
import subprocess
import sys
import tempfile
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


def attachment_pdf(cfg: Config, att: Attachment) -> Path | None:
    path = cfg.storage_root / att.key / att.filename
    return path if path.exists() else None


def pages(path: Path) -> int:
    info = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, text=True, check=False
    )
    match = re.search(r"Pages:\s+(\d+)", info.stdout)
    return int(match.group(1)) if match else 0


def evidence_images(path: Path, full: bool = False) -> list:
    """PIL page images: 1/2/middle for a lone PDF, cover page only for many."""
    from PIL import Image as PILImage

    total = pages(path)
    wanted = (
        sorted({1, 2, total // 2 + 1} & set(range(1, total + 1)))
        if full
        else [1]
    )
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in wanted:
            prefix = Path(tmp) / f"pg{n}"
            subprocess.run(
                ["pdftoppm", "-png", "-r", "60", "-f", str(n), "-l", str(n),
                 str(path), str(prefix)],
                check=False,
            )
            shots = sorted(
                prefix.parent.glob(f"{prefix.name}-*.png"),
                key=lambda p: int(p.stem.rsplit("-", 1)[-1]),
            )
            for shot in shots:
                out.append(PILImage.open(shot).copy())
    return out


def open_pdf(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
