"""Versioned JSON API for the premium product UI."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from pydantic import BaseModel

from spotdl.product.models import (
    AlbumEdition,
    ArtistSummary,
    ContentPreference,
    DownloadJobRecord,
    SearchResponse,
)
from spotdl.product.services import ProductServices

router = APIRouter(prefix="/api/v1", tags=["product-v1"])
SearchType = Literal["all", "album", "artist"]


class DownloadRequest(BaseModel):
    content_preference: ContentPreference = "explicit_only"


class ProductSettings(BaseModel):
    content_preference: ContentPreference = "explicit_only"


def get_services(request: Request) -> ProductServices:
    services = getattr(request.app.state, "product_services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Product services are not initialized")
    return services


@router.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=300),
    type: SearchType = "all",  # pylint: disable=redefined-builtin
    content_preference: ContentPreference | None = None,
) -> SearchResponse:
    services = get_services(request)
    preference = content_preference or services.store.get_setting(
        "content_preference", "explicit_only"
    )
    if preference not in {"explicit_only", "prefer_explicit", "any"}:
        preference = "explicit_only"

    albums = []
    artists = []
    if type in {"all", "album"}:
        albums = services.discovery.search_albums(q, preference=preference)
    if type in {"all", "artist"}:
        artists = services.discovery.search_artists(q)
    return SearchResponse(
        query=q,
        content_preference=preference,
        albums=albums,
        artists=artists,
    )


@router.get("/albums/{album_id}", response_model=AlbumEdition)
def get_album(album_id: str, request: Request) -> AlbumEdition:
    try:
        return get_services(request).discovery.album(album_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Album not found") from exc


@router.get("/artists/{artist_id}", response_model=ArtistSummary)
def get_artist(artist_id: str, request: Request) -> ArtistSummary:
    try:
        return get_services(request).discovery.artist(artist_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Artist not found") from exc


@router.get("/artists/{artist_id}/albums", response_model=list[AlbumEdition])
def get_artist_albums(
    artist_id: str,
    request: Request,
    content_preference: ContentPreference | None = None,
) -> list[AlbumEdition]:
    services = get_services(request)
    preference = content_preference or services.store.get_setting(
        "content_preference", "explicit_only"
    )
    if preference not in {"explicit_only", "prefer_explicit", "any"}:
        preference = "explicit_only"
    return services.discovery.artist_albums(artist_id, preference=preference)


@router.post(
    "/downloads/albums/{album_id}",
    response_model=DownloadJobRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_album_download(
    album_id: str,
    payload: DownloadRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> DownloadJobRecord:
    services = get_services(request)
    try:
        job = services.jobs.create_album_job(album_id, payload.content_preference)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Album not found") from exc
    background_tasks.add_task(services.jobs.run_job, job.job_id)
    return job


@router.get("/downloads", response_model=list[DownloadJobRecord])
def list_downloads(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    return get_services(request).store.list_jobs(limit=limit)


@router.get("/downloads/{job_id}", response_model=DownloadJobRecord)
def get_download(job_id: str, request: Request) -> DownloadJobRecord:
    job = get_services(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job


@router.post("/downloads/{job_id}/cancel", response_model=DownloadJobRecord)
def cancel_download(job_id: str, request: Request) -> DownloadJobRecord:
    try:
        return get_services(request).jobs.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Download job not found") from exc


@router.post("/downloads/{job_id}/retry", response_model=DownloadJobRecord)
def retry_download(
    job_id: str, background_tasks: BackgroundTasks, request: Request
) -> DownloadJobRecord:
    services = get_services(request)
    try:
        job = services.jobs.retry(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Download job not found") from exc
    background_tasks.add_task(services.jobs.run_job, job.job_id)
    return job


@router.get("/settings", response_model=ProductSettings)
def get_settings(request: Request) -> ProductSettings:
    preference = get_services(request).store.get_setting(
        "content_preference", "explicit_only"
    )
    if preference not in {"explicit_only", "prefer_explicit", "any"}:
        preference = "explicit_only"
    return ProductSettings(content_preference=preference)


@router.patch("/settings", response_model=ProductSettings)
def patch_settings(payload: ProductSettings, request: Request) -> ProductSettings:
    get_services(request).store.set_setting(
        "content_preference", payload.content_preference
    )
    return payload
