"""
Main application entry point.
"""

from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.models import BatteryIDs
from app import data

from .config import (
    VERSION,
    APP_DOCS_DIR,
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    FAVICON_PATH,
    STATIC_PATH,
)

app = FastAPI(
    title="Battery Capacity Monitor",
    description="View and query battery SoC information from a Battery Capacity Meter",
    version=VERSION,
    # The favicon is not settable in version 0.115.8 because there is no way to
    # pass a favicon path through to the swagger html generator.
    swagger_favicon_url=FAVICON_PATH,
)

# Mount the APP API docs?
if MOUNT_APP_DOCS:
    app.mount(
        f"/{APP_DOCS_PATH}",
        StaticFiles(directory=APP_DOCS_DIR, html=True, follow_symlink=True),
        name="app-docs",
    )

app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/")
def readRoot():
    """
    Handler for the root path.
    """
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def readItem(item_id: int, q: Union[str, None] = None):
    """
    Handler for the get items path.
    """
    return {"item_id": item_id, "q": q}


@app.get("/battery_ids")
def batteryIDs() -> BatteryIDs:
    """
    Returns a list of all knows Battery IDs.
    """
    return data.getAllBatIDs()
