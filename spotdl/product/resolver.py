"""Strict source resolution for the product UI without changing spotDL's CLI matcher."""

from typing import Any, Dict, List, Optional

from spotdl.product.explicit import filter_candidates
from spotdl.product.models import CandidateAssessment, ContentPreference
from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.formatter import create_search_query, create_song_title
from spotdl.utils.matching import order_results


class SourceResolutionError(LookupError):
    """Stable product-layer source lookup failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ExplicitSourceResolver:
    """Resolve audio using spotDL providers while enforcing content policy first."""

    def __init__(self, providers: List[Any]):
        self.providers = providers
        self.last_assessments: List[CandidateAssessment] = []

    @staticmethod
    def _verified(results: List[Result], only_verified: bool) -> List[Result]:
        if not only_verified:
            return results
        return [result for result in results if result.verified]

    def _allowed(
        self,
        song: Song,
        results: List[Result],
        preference: ContentPreference,
        only_verified: bool,
    ) -> List[Result]:
        results = self._verified(results, only_verified)
        allowed, assessments = filter_candidates(song, results, preference)
        self.last_assessments.extend(assessments)
        return allowed

    def _resolve_provider(
        self,
        provider: Any,
        song: Song,
        preference: ContentPreference,
        only_verified: bool,
    ) -> Optional[str]:
        search_query = create_song_title(song.name, song.artists).lower()
        if provider.search_query:
            search_query = create_search_query(
                song, provider.search_query, False, None, True
            )

        isrc_urls: List[str] = []
        if (
            song.isrc
            and getattr(provider, "SUPPORTS_ISRC", False)
            and not provider.search_query
        ):
            isrc_results = self._allowed(
                song,
                list(provider.get_results(song.isrc)),
                preference,
                only_verified,
            )
            isrc_urls = [result.url for result in isrc_results]

            if len(isrc_results) == 1 and isrc_results[0].verified:
                return isrc_results[0].url

            if isrc_results:
                ordered_isrc = order_results(isrc_results, song, provider.search_query)
                if ordered_isrc:
                    best_result, best_score = provider.get_best_result(ordered_isrc)
                    if best_score > 80.0:
                        return best_result.url

        accumulated: Dict[Result, float] = {}
        for options in provider.GET_RESULTS_OPTS:
            candidates = self._allowed(
                song,
                list(provider.get_results(search_query, **options)),
                preference,
                only_verified,
            )
            if not candidates:
                continue

            isrc_result = next(
                (result for result in candidates if result.url in isrc_urls), None
            )
            if isrc_result is not None:
                return isrc_result.url

            if provider.filter_results:
                ordered = order_results(candidates, song, provider.search_query)
            else:
                ordered = {candidates[0]: 100.0}

            if not ordered:
                continue

            best_result, best_score = provider.get_best_result(ordered)
            if best_score >= 80 and best_result.verified:
                return best_result.url
            accumulated.update(ordered)

        if not accumulated:
            return None

        best_result, _ = provider.get_best_result(accumulated)
        return best_result.url

    def resolve(
        self,
        song: Song,
        *,
        preference: ContentPreference = "explicit_only",
        only_verified: bool = False,
    ) -> str:
        """Resolve one song or raise a stable failure suitable for `needs_review`."""

        self.last_assessments = []
        for provider in self.providers:
            url = self._resolve_provider(provider, song, preference, only_verified)
            if url:
                return url

        if song.explicit is True and preference == "explicit_only":
            raise SourceResolutionError(
                "no_explicit_source",
                f"No explicit-compatible source found for {song.display_name}",
            )
        raise SourceResolutionError(
            "source_unavailable", f"No source found for {song.display_name}"
        )
