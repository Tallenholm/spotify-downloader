"""Runtime assembly for product services used by the web application."""

import asyncio
from typing import Optional

from spotdl.download.downloader import Downloader
from spotdl.product.discovery import DiscoveryService
from spotdl.product.jobs import DownloadJobManager
from spotdl.product.resolver import ExplicitSourceResolver
from spotdl.product.services import ProductServices
from spotdl.product.store import ProductStore
from spotdl.types.options import DownloaderOptions
from spotdl.utils.config import get_spotdl_path


def build_product_services(
    downloader_settings: DownloaderOptions,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> ProductServices:
    """Build isolated product services without changing legacy CLI settings."""

    store = ProductStore(get_spotdl_path() / "product.db")
    if store.get_setting("content_preference") is None:
        store.set_setting("content_preference", "explicit_only")

    search_downloader = Downloader(settings=downloader_settings, loop=loop)
    resolver = ExplicitSourceResolver(search_downloader.audio_providers)

    def downloader_factory() -> Downloader:
        return Downloader(settings=downloader_settings, loop=loop)

    jobs = DownloadJobManager(
        store=store,
        discovery=DiscoveryService(),
        resolver=resolver,
        downloader_factory=downloader_factory,
        only_verified=downloader_settings["only_verified_results"],
    )
    return ProductServices(store=store, discovery=jobs.discovery, jobs=jobs)
