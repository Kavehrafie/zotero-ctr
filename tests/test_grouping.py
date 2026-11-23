from fixtures import ITEMS
from grouping import entry_key, find_groups


def test_fuzzy_cluster_survives_pruning():
    assert any(k[0] == "fuzzy" for k in find_groups(ITEMS, entry_key))
