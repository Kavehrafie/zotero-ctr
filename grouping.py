import re
from collections import defaultdict
from difflib import SequenceMatcher

from models import Attachment, Item

FUZZY_THRESHOLD = 0.85


def normalize(title: str) -> str:
    t = title.split(":")[0].strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    return "".join(ch for ch in t if ch.isalnum())


def entry_key(item: Item) -> tuple | None:
    if item.doi:
        return "doi", item.doi.lower()
    if title := normalize(item.title):
        return "title+year", title, item.year
    return None


def attachment_key(att: Attachment) -> tuple[str, str]:
    return "md5", att.md5


def fuzzy_merged(groups):
    candidates = [k for k in groups if len(k) == 3 and k[2] is not None]
    parent = {k: k for k in candidates}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, k1 in enumerate(candidates):
        for k2 in candidates[i + 1 :]:
            if k1[2] != k2[2]:
                continue
            lo, hi = sorted((len(k1[1]), len(k2[1])))
            if 2 * lo / (lo + hi) <= FUZZY_THRESHOLD:
                continue
            sm = SequenceMatcher(a=k1[1], b=k2[1])
            if sm.quick_ratio() >= FUZZY_THRESHOLD and sm.ratio() >= FUZZY_THRESHOLD:
                parent[find(k2)] = find(k1)
    out = {k: v for k, v in groups.items() if k not in parent}
    clusters = defaultdict(list)
    for k in candidates:
        clusters[find(k)].append(k)
    for keys in clusters.values():
        if len(keys) > 1:
            out[("fuzzy", keys[0][1], keys[0][2])] = [
                m for k in keys for m in groups[k]
            ]
        else:
            out[keys[0]] = groups[keys[0]]

    return out


def dups_only(groups):
    return {k: v for k, v in groups.items() if len(v) > 1}


def wildcard_merged(groups):
    per_title = defaultdict(dict)
    out = {}
    for key, numbers in groups.items():
        if len(key) == 2:  # doi, md5 — already exact
            out[key] = numbers
        else:
            per_title[key[1]][key[2]] = numbers
    for title, years in per_title.items():
        if None in years:
            out[("title", title)] = [m for ms in years.values() for m in ms]
        else:
            for year, members in years.items():
                out[("title+year", title, year)] = members
    return out


def find_groups(entries, key_of):
    groups = defaultdict(list)
    for entry in entries:
        if key := key_of(entry):
            groups[key].append(entry)
    return dups_only(fuzzy_merged(wildcard_merged(groups)))


def pick_master(members):
    return min(members, key=lambda e: e.key)
