"""
Main application entry point.
"""

from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import (
    APP_DOCS_DIR,
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
)

app = FastAPI()

# Mount the APP API docs?
if MOUNT_APP_DOCS:
    app.mount(
        f"/{APP_DOCS_PATH}",
        StaticFiles(directory=APP_DOCS_DIR, html=True, follow_symlink=True),
        name="app-docs",
    )


@app.get("/")
def read_root():
    """
    Handler for the root path.
    """
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    """
    Handler for the get items path.
    """
    return {"item_id": item_id, "q": q}
