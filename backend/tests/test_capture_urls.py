import pytest

from annotool.capture.urls import (
    UrlEntry,
    UrlListError,
    entries_from_sources,
    page_id_for_url,
    read_url_list,
)

# ── Page ids ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "page_id"),
    [
        # Same ids as the legacy captures, so old and new pages line up.
        ("https://www.adobe.com", "www_adobe_com"),
        ("https://edition.cnn.com/", "edition_cnn_com"),
        ("https://khanacademy.org", "khanacademy_org"),
        ("https://WWW.Example.COM:8080/", "www_example_com"),
        ("https://www.example.com/products/shoes/", "www_example_com-products-shoes"),
        ("https://www.example.com/a b/C%20d.html", "www_example_com-a-b-c-20d-html"),
        ("https://www.example.com/search?q=shoes#top", "www_example_com-search"),
        ("file:///C:/tmp/fixtures/sticky.html", "file-sticky"),
    ],
)
def test_page_id_for_url(url, page_id):
    assert page_id_for_url(url) == page_id


def test_long_paths_are_shortened_but_stay_distinct():
    a = page_id_for_url("https://example.com/" + "a" * 200 + "/one")
    b = page_id_for_url("https://example.com/" + "a" * 200 + "/two")
    assert len(a) <= 100 and len(b) <= 100
    assert a != b


# ── URL lists ────────────────────────────────────────────────────────────────


def test_reads_the_legacy_url_list_format(tmp_path):
    csv = tmp_path / "urls.csv"
    csv.write_text(
        "Category,Website URL\nNews & Media,https://www.bbc.com\nE-commerce,https://www.amazon.com\n",
        encoding="utf-8",
    )
    assert read_url_list(csv) == [
        UrlEntry(url="https://www.bbc.com", category="News & Media"),
        UrlEntry(url="https://www.amazon.com", category="E-commerce"),
    ]


def test_reads_optional_page_type_and_skips_blank_rows(tmp_path):
    csv = tmp_path / "urls.csv"
    csv.write_text(
        "\ufeffurl,category,page_type\n"  # BOM, as Excel writes it
        "https://shop.com/item/1,E-commerce,item detail\n"
        ",,\n",
        encoding="utf-8",
    )
    assert read_url_list(csv) == [
        UrlEntry(url="https://shop.com/item/1", category="E-commerce", page_type="item detail")
    ]


def test_url_list_without_url_column_is_an_error(tmp_path):
    csv = tmp_path / "urls.csv"
    csv.write_text("Category,Site\nNews,https://x.com\n", encoding="utf-8")
    with pytest.raises(UrlListError, match="URL column"):
        read_url_list(csv)


def test_sources_mix_urls_and_csv_files(tmp_path):
    csv = tmp_path / "urls.csv"
    csv.write_text("Category,Website URL\nNews,https://www.bbc.com\n", encoding="utf-8")
    entries = entries_from_sources(["https://www.adobe.com", str(csv)])
    assert [e.url for e in entries] == ["https://www.adobe.com", "https://www.bbc.com"]


def test_duplicate_page_ids_are_an_error(tmp_path):
    with pytest.raises(UrlListError, match="www_adobe_com"):
        entries_from_sources(["https://www.adobe.com", "https://www.adobe.com/"])


def test_source_that_is_neither_url_nor_file_is_an_error():
    with pytest.raises(UrlListError, match="adobe.com"):
        entries_from_sources(["adobe.com"])
