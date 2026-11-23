import re

STOP = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
TAGS = re.compile(r"\s*</?(i|em|b|strong|sub|sup|span)>\s*")


def strip_tags(title: str) -> str:
    return TAGS.sub(" ", title).strip()


def fix_case(title: str) -> str:
    words = title.split()
    letters = [c for c in title if c.isalpha()]
    if (
        not words
        or len(title) <= 6
        or sum(c.isupper() for c in letters) / len(letters) <= 0.7
    ):
        return title
    return " ".join(
        w.lower()
        if i and i != len(words) - 1 and w.lower().strip(":,") in STOP
        else w.capitalize()
        for i, w in enumerate(words)
    )


def tidy(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def clean_title(title: str) -> str:
    return tidy(fix_case(strip_tags(title)))
