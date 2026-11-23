from models import Attachment, Creator, Item

ITEMS = [
    Item(
        key="A1",
        title="Textile Histories",
        year=2019,
        doi="10.2307/25154106",
        creator=Creator(first="Maya", last="Calder"),
    ),
    Item(
        key="B7",
        title="Textile Histories",
        year=2019,
        doi="10.2307/25154106",
        creator=Creator(first="Maya", last="Calder"),
    ),
    Item(
        key="C3",
        title="Weaving the Nation",
        year=2017,
        item_type="book",
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="D8",
        title="Weaving the Nation",
        year=2017,
        item_type="journalArticle",
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="E2",
        title="weaving the nation!",
        year=2017,
        creator=Creator(first="Ivan", last="Ortega"),
    ),
    Item(
        key="F4",
        title="The Loom and the Loomed",
        year=2021,
        creator=Creator(first="Sara", last="Kwon"),
    ),
    Item(
        key="G9",
        title="Dye Gardens of Oaxaca",
        year=2020,
        creator=Creator(first="Luca", last="Moretti"),
    ),
    Item(
        key="H5",
        title="Pigment and Empire",
        year=2015,
        doi="10.1017/s00104175",
        creator=Creator(first="Nora", last="Feld"),
    ),
    Item(
        key="J6",
        title="Pigment and Empire",
        year=2015,
        doi="10.1017/s00104175",
        creator=Creator(first="Nora", last="Feld"),
    ),
    Item(
        key="M4",
        title="Desert Solitaire",
        year=1968,
        creator=Creator(first="Edward", last="Abbey"),
    ),
    Item(
        key="N2",
        title="Desert Solitaire",
        creator=Creator(first="Edward", last="Abbey"),
    ),
    Item(key="K8", title="", creator=Creator(first="Anon", last="Ymous")),
    Item(
        key="P3",
        title="Dye Gardens of Oaxaka",
        year=2020,
        creator=Creator(first="Luca", last="Moretti"),
    ),
    Item(
        key="Q5",
        title="The Loom and the Loomed: Collected Essays",
        year=2021,
        creator=Creator(first="Sara", last="Kwon"),
    ),
]

ATTACHMENTS = [
    Attachment(key="X1", filename="textile-histories.pdf", md5="aa11", parent_key="A1"),
    Attachment(
        key="X2", filename="textile-histories (1).pdf", md5="aa11", parent_key="B7"
    ),
    Attachment(key="X3", filename="loom.pdf", md5="bb22", parent_key="F4"),
    Attachment(key="X4", filename="loom copy.pdf", md5="bb22", parent_key="F4"),
    Attachment(key="X5", filename="dye-gardens.pdf", md5="cc33", parent_key="G9"),
]
