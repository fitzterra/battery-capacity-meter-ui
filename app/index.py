"""
Functions to render the main index page with a given content subsection, and
also some support functions.
"""

from microdot.asgi import Response
from microdot.utemplate import Template

from .config import (
    VERSION,
    THEME_COLOR,
    BAT_IMG_MAX_SZ,
)


def errorResponse(msg):
    """
    Any URL handler that needs to flash an error message can call this
    function, passing in the error message and then returning the response
    generated here.

    The original handler must have been an HTMX request, meaning that HTMX is
    making the request, and will handle the response from the URL handler.

    For this to flash the message, an element with class ``err-flash`` must
    already be available in the DOM, like::

        <div class='err-flash'></div>

    In addition, some CSS is also needed::

        /* The global error flasher div */
        /* Base styles for the error flash */
        .err-flash {
          display: none; /* Initially hidden */
          padding: 0.8rem;
          margin: 0 0 0.5rem;
          border: 1px solid var(--pico-color-red-400);
          border-radius: var(--pico-border-radius);
          background-color: var(--pico-color-red-350);
          color: var(--pico-color-red-950);
          max-height: 0;
          overflow: hidden;
          transform: translateY(10px); /* Start below */
          transition: transform 0.3s ease, max-height 0.3s ease; /* Optional: control expansion timing */
        }

        /* When the error message is shown */
        .err-flash.visible {
          display: block;
          max-height: 200px; /* Allow the content to expand */
          transform: translateY(0); /* Reset the transform */
          transition: transform 0.8s ease, max-height 0.8s ease; /* Smooth expand */
          cursor: pointer;
        }

    The flow here will be:

    * The HTMX request is made to the handler, without changing anything in the DOM.
    * The handler deals with the request, but detects and error.
    * It calls this function passing in the error info
    * This function generates a small HTML snippet with the error info
    * In addition, it sets the ``HX-Retarget`` header to ``.err-flash`` which
      means the HTML response will be rendered in the element with this class
      name, which is our ``<div>`` from above.
    * HTMX receives the response, and renders the HTML snippet received.
    * CSS takes over, displays the error for a brief period and then removes it
      again.

    Args:
        msg: This is either a single string or a list of strings to flash as
            error message(s). If it's a list, it will be render as items in an
            unordered list (<ul>). The message(s) may contain minimal HTML
            markup if needed.
    """
    # Generate the output HTML
    if isinstance(msg, str):
        # A simple error message goes into a div
        html = f'<div class="message">{msg}</div>'
    else:
        # Multiple messages goes into a list
        html = '<ul class="message-list">'
        html += "".join([f"<li>{m}</li>" for m in msg])
        html += "</ul>"

    # Create Microdot Response
    response = Response(body=html)
    # We will change the target for the response to the .error container,
    # overriding any default target from the original request.
    response.headers["HX-Retarget"] = ".err-flash"

    return response


def renderIndex(content: str = ""):
    """
    Wrapper to render the full index template with optional content.

    Since we are passing certain context to the ``index.html`` template, it is
    better to abstract rendering to one function instead of having to repeat
    the context in all places we render ``index.html``.

    Args:
        content: Any content to render in the content section
    """

    return Template("index.html").render(
        content=content,
        version=VERSION,
        bat_img_max_sz=BAT_IMG_MAX_SZ,
        theme=THEME_COLOR,
    )
