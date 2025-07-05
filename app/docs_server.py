"""
App to server to application docs.

In order to server the docs, they need to be build first. This can be done
using the ``docs`` target in the ``Makefile``::

    $ make docs

This will build the API docs as a static site in the `APP_DOCS_DIR` path
relative to the repo root.

The `main` module will mount this `app` on the `APP_DOCS_PATH` URL prefix if
the `MOUNT_APP_DOCS` config option is set. This is mainly used for development
since the main deployment pipeline also publishes the full doc site

Attributes:
    app: Microdot_ sub app to handle all requests for doc and doc static files.

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import os
from microdot.asgi import Microdot, redirect, send_file

from app.config import (
    APP_DOCS_DIR,
)

app = Microdot()


@app.get("/")
async def appDocsIndex(_):
    """
    App docs root - we just redirect to the ``index.html`` relative to the base
    dir.
    """
    return redirect("index.html")


@app.get("/<path:path>")
async def appDocs(_, path: str):
    """
    Servers any file on the `APP_DOCS_PATH` URL as a static file.

    This will allow any of the static files in the `APP_DOCS_DIR` to be served
    via this handler.

    For security, we do not allow dir hopping via ``..`` elements in the path,
    and any file requested that is not available will return a 404, Not Found
    response.

    Args:
        _: Disregarded ``Request`` object
        path: The full URL path as a string
    """
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    f_path = f"{APP_DOCS_DIR}/{path}"
    if not os.path.exists(f_path) or os.path.isdir(f_path):
        return "Not found", 404
    return send_file(f_path, max_age=86400)
