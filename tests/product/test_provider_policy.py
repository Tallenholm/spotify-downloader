from spotdl.providers.audio.base import AudioProvider
from spotdl.types.result import Result
from spotdl.types.song import Song


def make_song() -> Song:
    return Song.from_missing_data(
        name="Example Song",
        artists=["Example Artist"],
        artist="Example Artist",
        album_name="Example Album",
        album_artist="Example Artist",
        duration=200,
        song_id="spotify-track",
        explicit=True,
        url="https://open.spotify.com/track/spotify-track",
    )


def result(result_id: str, *, explicit: bool | None, name: str = "Example Song") -> Result:
    return Result(
        source="FakeProvider",
        url=f"https://example.test/{result_id}",
        verified=True,
        name=name,
        duration=200,
        author="Example Artist",
        artists=("Example Artist",),
        result_id=result_id,
        explicit=explicit,
        views=100,
    )


class FakeProvider(AudioProvider):
    SUPPORTS_ISRC = False
    GET_RESULTS_OPTS = [{}]

    def __init__(self, results):
        self.results = results
        self.search_query = None
        self.filter_results = True

    def get_results(self, _search_term, **_kwargs):
        return list(self.results)

    def get_views(self, _url):
        return 100


def test_explicit_only_selects_explicit_result_over_clean_result():
    provider = FakeProvider(
        [
            result("clean", explicit=False),
            result("explicit", explicit=True),
        ]
    )

    selected = provider.search(make_song(), content_preference="explicit_only")

    assert selected == "https://example.test/explicit"


def test_explicit_only_returns_none_when_only_clean_result_exists():
    provider = FakeProvider([result("clean", explicit=False)])

    selected = provider.search(make_song(), content_preference="explicit_only")

    assert selected is None


def test_explicit_only_returns_none_for_ambiguous_unmarked_result():
    provider = FakeProvider([result("unknown", explicit=None)])

    selected = provider.search(make_song(), content_preference="explicit_only")

    assert selected is None


def test_any_preserves_unknown_candidate():
    provider = FakeProvider([result("unknown", explicit=None)])

    selected = provider.search(make_song(), content_preference="any")

    assert selected == "https://example.test/unknown"
