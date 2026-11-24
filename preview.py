import os
import re
import shutil
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


def thumbnail(path: Path) -> None:
    """Evidence view: first two pages plus one middle page, in a grid."""
    if not shutil.which("timg"):
        if sys.platform == "win32":
            os.startfile(path)  # no timg here – open the PDF instead
        else:
            print("(timg not installed – sudo dnf install timg)")
        return
    if shutil.which("pdftoppm"):
        _evidence_grid(path)
        return
    subprocess.run(["timg", str(path)], check=False)


def _evidence_grid(path: Path) -> None:
    total = pages(path)
    picks = sorted({1, 2, total // 2 + 1} & set(range(1, total + 1)))
    with tempfile.TemporaryDirectory() as tmp:
        shots = []
        for n in picks:
            prefix = Path(tmp) / f"pg{n}"
            subprocess.run(
                ["pdftoppm", "-png", "-r", "60", "-f", str(n), "-l", str(n),
                 str(path), str(prefix)],
                check=False,
            )
            shots += sorted(
                prefix.parent.glob(f"{prefix.name}-*.png"),
                key=lambda p: int(p.stem.rsplit("-", 1)[-1]),
            )
        if shots:
            subprocess.run(
                ["timg", f"--grid={len(shots)}x1", *(str(s) for s in shots)], check=False
            )


def open_pdf(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
