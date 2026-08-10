"""
Web module for the console.
"""

import asyncio
import logging
import shutil
import signal
import sys
import webbrowser
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from spotdl._version import __version__
from spotdl.product.runtime import build_product_services
from spotdl.types.options import DownloaderOptions, WebOptions
from spotdl.utils.config import get_spotdl_path, get_web_ui_path
from spotdl.utils.logging import NAME_TO_LEVEL
from spotdl.utils.web import (
    ALLOWED_ORIGINS,
    SPAStaticFiles,
    app_state,
    fix_mime_types,
    get_current_state,
)
from spotdl.web import api, product_api, routes

__all__ = ["web"]

logger = logging.getLogger(__name__)


def web(web_settings: WebOptions, downloader_settings: DownloaderOptions):
    """Run the local web server."""

    fix_mime_types()

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.propagate = False
    spotipy_logger = logging.getLogger("spotipy")
    spotipy_logger.setLevel(logging.NOTSET)

    app_state.web_settings = web_settings
    app_state.logger = uvicorn_logger
    app_state.loop = (
        asyncio.new_event_loop()
        if sys.platform != "win32"
        else asyncio.ProactorEventLoop()  # type: ignore
    )

    downloader_settings["simple_tui"] = True
    app_state.downloader_settings = downloader_settings

    app_state.api = FastAPI(
        title="spotDL",
        description="Download music from Spotify",
        version=__version__,
        dependencies=[Depends(get_current_state)],
    )
    app_state.api.state.product_services = build_product_services(
        downloader_settings, app_state.loop
    )

    app_state.api.include_router(api.router)
    app_state.api.include_router(product_api.router)
    # Keep the legacy server-rendered UI registered until the React SPA reaches parity.
    app_state.api.include_router(routes.router)

    app_state.api.add_middleware(
        CORSMiddleware,
        allow_origins=(
            ALLOWED_ORIGINS + web_settings["allowed_origins"]
            if web_settings["allowed_origins"]
            else ALLOWED_ORIGINS
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    web_app_dir = get_web_ui_path()
    app_state.api.mount(
        "/assets",
        SPAStaticFiles(directory=web_app_dir / "assets", html=True),
        name="static",
    )

    protocol = "http"
    config = Config(
        app=app_state.api,
        host=web_settings["host"],
        port=web_settings["port"],
        log_level=NAME_TO_LEVEL[downloader_settings["log_level"]],
        loop=app_state.loop,  # type: ignore
    )
    if web_settings["enable_tls"]:
        logger.info("Enabling TLS")
        protocol = "https"
        config.ssl_certfile = web_settings["cert_file"]
        config.ssl_keyfile = web_settings["key_file"]
        config.ssl_ca_certs = web_settings["ca_file"]

    app_state.server = Server(config)
    webbrowser.open(f"{protocol}://{web_settings['host']}:{web_settings['port']}/")

    if not web_settings["web_use_output_dir"]:
        logger.info(
            "Legacy web-session downloads use the temporary directory; "
            "the premium product queue uses configured downloader output paths."
        )

    logger.info("Starting web server \n")

    def handle_shutdown(signum, frame):  # pylint: disable=unused-argument
        app_state.server.should_exit = True

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        app_state.loop.run_until_complete(app_state.server.serve())
    finally:
        product_services = getattr(app_state.api.state, "product_services", None)
        if product_services is not None:
            product_services.store.close()
        if (
            not app_state.web_settings["keep_sessions"]
            and not app_state.web_settings["web_use_output_dir"]
        ):
            sessions_dir = Path(get_spotdl_path() / "web/sessions")
            logger.info("Removing sessions directories")
            if sessions_dir.exists():
                shutil.rmtree(sessions_dir)
