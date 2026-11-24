from fixtures import ATTACHMENTS, ITEMS
from grouping import entry_key, find_groups, pick_master
from models import Item
from plan import FreeLocal, Trash, Write, describe, plan_delete, plan_free, plan_merge


def test_plan_delete_keeps_master():
    members = next(iter(find_groups(ITEMS, entry_key).values()))
    master = pick_master(members)
    assert {c.key for c in plan_delete(members)} == {m.key for m in members} - {
        master.key
    }


def test_plan_merge_reparents_and_trahses():
    master, dup = ITEMS[0], ITEMS[1]
    plan = plan_merge(master, [dup], ATTACHMENTS)
    assert Write("X2", {"parentItem": "A1"}) in plan
    assert Trash("B7") in plan


def test_plan_merge_fills_empty_first_dup_wins():
    master = Item(key="M1", title="T")
    d1 = Item(key="D1", title="T", doi="10.1/x", publisher="P")
    d2 = Item(
        key="D2",
        title="T",
        doi="10.1/y",
    )
    plan = plan_merge(master, [d1, d2], [])
    assert Write("M1", {"DOI": "10.1/x", "publisher": "P"}) in plan
    assert not any(
        c.changes.get("DOI") == "10.1/y" for c in plan if isinstance(c, Write)
    )


def test_plan_free_skip_missing_folders(tmp_path):
    assert plan_free([ITEMS[0]], {"A1": ATTACHMENTS[:1]}, tmp_path) == []


def test_describe_lines():
    assert describe(Trash("B7")) == "trash B7"
    assert describe(Write("A1", {"DOI": "x"})) == "write A1: DOI = x"
    assert (
        describe(Write("M1", {"DOI": "10.1/x", "publisher": "P"}))
        == "write M1: DOI = 10.1/x, publisher = P"
    )
    assert describe(FreeLocal("X1", 2_400_000)) == "free X1 (2.4 MB)"
