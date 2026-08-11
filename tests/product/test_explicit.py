from spotdl.product.explicit import assess_candidate, classify_edition
from spotdl.types.result import Result
from spotdl.types.song import Song


def make_song(*, explicit: bool) -> Song:
    return Song.from_missing_data(
        name="Example Song",
        artists=["Example Artist"],
        artist="Example Artist",
        album_name="Example Album",
        album_artist="Example Artist",
        duration=201,
        song_id="spotify-track",
        explicit=explicit,
        url="https://open.spotify.com/track/spotify-track",
    )


def make_result(*, name: str, explicit: bool | None) -> Result:
    return Result(
        source="YouTubeMusic",
        url=f"https://music.youtube.com/watch?v={name.replace(' ', '-')}",
        verified=True,
        name=name,
        duration=201,
        author="Example Artist",
        result_id=name,
        explicit=explicit,
    )


def test_explicit_only_rejects_provider_marked_clean_candidate():
    assessment = assess_candidate(
        make_song(explicit=True),
        make_result(name="Example Song", explicit=False),
        "explicit_only",
    )

    assert assessment.accepted is False
    assert assessment.reason == "explicit_required_clean_candidate"


def test_explicit_only_rejects_clean_title_even_when_provider_flag_unknown():
    assessment = assess_candidate(
        make_song(explicit=True),
        make_result(name="Example Song (Clean)", explicit=None),
        "explicit_only",
    )

    assert assessment.accepted is False
    assert assessment.reason == "explicit_required_clean_candidate"


def test_explicit_only_accepts_provider_marked_explicit_candidate():
    assessment = assess_candidate(
        make_song(explicit=True),
        make_result(name="Example Song", explicit=True),
        "explicit_only",
    )

    assert assessment.accepted is True
    assert assessment.reason == "explicit_candidate"


def test_non_explicit_song_is_not_filtered_by_explicit_only_policy():
    assessment = assess_candidate(
        make_song(explicit=False),
        make_result(name="Example Song", explicit=False),
        "explicit_only",
    )

    assert assessment.accepted is True
    assert assessment.reason == "content_policy_not_required"


def test_non_explicit_release_is_not_mislabeled_clean_without_explicit_sibling():
    assert classify_edition([False, False, False], sibling_has_explicit=False) == "non_explicit"


def test_non_explicit_release_is_clean_when_explicit_sibling_exists():
    assert classify_edition([False, False, False], sibling_has_explicit=True) == "clean"


def test_release_with_any_explicit_track_is_explicit():
    assert classify_edition([False, True, False], sibling_has_explicit=False) == "explicit"
