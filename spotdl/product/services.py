"""Small dependency container for product API services."""

from dataclasses import dataclass
from typing import Any

from spotdl.product.discovery import DiscoveryService
from spotdl.product.jobs import DownloadJobManager
from spotdl.product.store import ProductStore


@dataclass
class ProductServices:
    """Services attached to FastAPI application state."""

    store: ProductStore
    discovery: DiscoveryService
    jobs: DownloadJobManager | Any
