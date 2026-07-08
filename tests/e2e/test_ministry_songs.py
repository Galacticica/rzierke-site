"""
File: test_ministry_songs.py
Description: Song library: pagination and search via HTMX, the detail page,
and the PPTX/PDF export downloads. Uses the 30-song `songs` fixture
(25 per page, so page 2 has 5 rows).
"""

from playwright.sync_api import Page, expect

SONG_ROW = '[data-testid="song-row"]'


def test_song_list_paginates_25_per_page(page: Page, live_server, songs):
    page.goto(live_server.url + "/ministry/songs/")

    expect(page.locator(SONG_ROW)).to_have_count(25)
    expect(page.locator('[data-testid="song-pagination"]')).to_be_visible()


def test_pagination_page_two_swaps_rows(page: Page, live_server, songs):
    page.goto(live_server.url + "/ministry/songs/")
    expect(page.locator(SONG_ROW)).to_have_count(25)

    page.locator('[data-testid="song-pagination"]').get_by_role("link", name="2", exact=True).click()

    expect(page.locator(SONG_ROW)).to_have_count(5)
    expect(page.locator("body")).to_contain_text("Song Number 30")
    assert "page=2" in page.url  # hx-push-url


def test_search_filters_songs(page: Page, live_server, songs):
    page.goto(live_server.url + "/ministry/songs/")
    expect(page.locator(SONG_ROW)).to_have_count(25)

    page.fill('input[name="q"]', "Song Number 07")
    page.get_by_role("button", name="Search").click()

    expect(page.locator(SONG_ROW)).to_have_count(1)
    expect(page.locator(SONG_ROW)).to_contain_text("Song Number 07")


def test_song_detail_page_opens_from_list(page: Page, live_server, songs):
    page.goto(live_server.url + "/ministry/songs/")

    page.get_by_role("link", name="Song Number 01", exact=True).click()

    expect(page).to_have_url(live_server.url + "/ministry/songs/song-number-01/")
    expect(page.get_by_role("heading", name="Song Number 01")).to_be_visible()


def _make_exportable(song):
    """Export buttons only render for public-domain songs; give it lyrics too."""
    from ministry.models import SectionDefinition

    song.public_domain = True
    song.save(update_fields=["public_domain"])
    SectionDefinition.objects.create(
        song=song,
        section_type=SectionDefinition.VERSE,
        lyrics="Amazing grace how sweet the sound\nThat saved a wretch like me",
    )
    return song


def test_pptx_export_download(page: Page, live_server, songs, tmp_path):
    song = _make_exportable(songs[0])  # Song Number 01

    page.goto(live_server.url + f"/ministry/songs/{song.slug}/")
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Export Slides").click()
    download = download_info.value

    assert download.suggested_filename.endswith(".pptx")
    target = tmp_path / download.suggested_filename
    download.save_as(target)
    assert target.read_bytes()[:2] == b"PK"


def test_pdf_handout_download(page: Page, live_server, songs, tmp_path):
    song = _make_exportable(songs[1])  # Song Number 02

    page.goto(live_server.url + f"/ministry/songs/{song.slug}/")
    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download PDF").click()
    download = download_info.value

    # views.SongPrintPDFView names the file "<slug>-handout.pdf".
    assert download.suggested_filename.endswith("handout.pdf")
    assert download.suggested_filename == f"{song.slug}-handout.pdf"
    target = tmp_path / download.suggested_filename
    download.save_as(target)
    assert target.read_bytes()[:4] == b"%PDF"
