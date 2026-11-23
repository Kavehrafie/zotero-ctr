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
    letters = [c for c in title if c.isalpha()]
    if (
        not letters
        or len(title) <= 6
        or sum(c.isupper() for c in letters) / len(letters) <= 0.7
    ):
        return title
    out, cap_next = [], True
    for w in title.split():
        out.append(w.capitalize() if cap_next else w.lower())
        cap_next = w.endswith(":")
    return " ".join(out)

def tidy(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def clean_title(title: str) -> str:
    return tidy(fix_case(strip_tags(title)))

def split_creators(creators: list[dict]) -> list[str]:
    out = []
    for c in creators:
        name = c.get("name") or ""
        if ", " in name:
            last, _, first = name.partition(", ")
            c = {k: v for k, v in c.items() if k != "name"}
            c["firstName"], c["lastName"] = first, last
        out.append(c)
    return out