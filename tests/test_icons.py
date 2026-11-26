from icons import DOC, EPUB, FILE, IMAGE, PDF, WEB, file_icon


def test_content_type_wins_over_filename():
    assert file_icon("noext", "application/pdf") == PDF
    assert file_icon("foo.html", "application/epub+zip") == EPUB


def test_suffix_fallback_and_generic():
    assert file_icon("paper.PDF") == PDF
    assert file_icon("readme.md") == DOC
    assert file_icon("shot.png") == IMAGE
    assert file_icon("snapshot.html") == WEB
    assert file_icon("thesis.epub") == EPUB
    assert file_icon("thing.bin") == FILE
    assert file_icon("noext") == FILE
