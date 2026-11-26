"""Nerd Font glyphs for attachment types — all in the fa- range: the only set
this user's Kitty draws reliably (seti/cod square out despite charset
coverage); every glyph PIL-verified against the font file."""

from pathlib import Path

PDF = "\U0000F1C1"  # fa-file-pdf-o
EPUB = "\U0000F097"  # fa-bookmark
WEB = "\U0000F0AC"  # fa-globe
WORD = "\U0000F1C2"  # fa-file-word-o
IMAGE = "\U0000F1C5"  # fa-file-image-o
DOC = "\U0000F0F6"  # fa-file-text-o
ZIP = "\U0000F1C6"  # fa-file-archive-o
FILE = "\U0000F016"  # fa-file-o

CONTENT = {
    "application/pdf": PDF,
    "application/epub": EPUB,
    "application/x-mobipocket": EPUB,
    "text/html": WEB,
    "application/msword": WORD,
    "application/vnd.openxmlformats": WORD,
    "image/": IMAGE,
    "audio/": FILE,
    "video/": FILE,
}

EXTS = {
    ".pdf": PDF,
    ".epub": EPUB,
    ".mobi": EPUB,
    ".azw": EPUB,
    ".azw3": EPUB,
    ".html": WEB,
    ".htm": WEB,
    ".doc": WORD,
    ".docx": WORD,
    ".rtf": WORD,
    ".png": IMAGE,
    ".jpg": IMAGE,
    ".jpeg": IMAGE,
    ".gif": IMAGE,
    ".tif": IMAGE,
    ".tiff": IMAGE,
    ".djvu": IMAGE,
    ".txt": DOC,
    ".md": DOC,
    ".zip": ZIP,
}


def file_icon(name: str, content_type: str = "") -> str:
    """Glyph for an attachment: Zotero's contentType first, filename fallback."""
    for prefix, glyph in CONTENT.items():
        if content_type.startswith(prefix):
            return glyph
    return EXTS.get(Path(name).suffix.lower(), FILE)
