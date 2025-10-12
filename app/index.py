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


def flashMessage(msg, msg_type=None):
    """
    Any URL handler that needs to flash a message can call this function,
    passing in the message and an optional message type, and then returning the
    response generated here to the browser.

    The original handler must have been an HTMX request, meaning that HTMX is
    making the request, and will handle the response from the URL handler.

    For this to flash the message, an element with class ``msg-flash`` must
    already be available in the DOM, like::

        <div class='msg-flash'></div>

    In addition, some CSS is also needed::

        /* -- END: Message flasher -- */
        /* Base styles for the message flash */
        .msg-flash {
          display: none; /* Initially hidden */
          padding: 0.8rem;
          margin: 0 0 0.5rem;
          border: 1px solid var(--pico-primary-border);
          border-radius: var(--pico-border-radius);
          max-height: 0;
          overflow: hidden;
          transform: translateY(10px); /* Start below */
          transition: transform 0.3s ease, max-height 0.3s ease; /* Optional: control expansion timing */
        }

        /* When the message is shown */
        .msg-flash.visible {
          display: block;
          max-height: 200px; /* Allow the content to expand */
          transform: translateY(0); /* Reset the transform */
          transition: transform 0.8s ease, max-height 0.8s ease; /* Smooth expand */
          cursor: pointer;
        }

        /* Here we can add colors and visuals based on the classes add to the child
         * element for the main flash container - this corresponds to the
         * msg_type arg */
        .msg-flash:has(.error) {
          background-color: var(--pico-color-red-350);
          color: var(--pico-color-red-950);
          border-color: var(--pico-color-red-400);
        }
        .msg-flash:has(.success) {
          background-color: var(--pico-color-green-350);
          color: var(--pico-color-green-950);
          border-color: var(--pico-color-green-400);
        }


    The flow here will be:

    * The HTMX request is made to the handler, without changing anything in the DOM.
    * The handler deals with the request, and want to flash a message (success,
      error, etc.) without returning any other content.
    * It calls this function passing in the message info, and a ``msg_type`` of
      ``success``, ``error``, etc. As long as there is CSS to handle this type
      of message and alter the message display, any message type can be added.
    * This function generates a small HTML snippet with the message info, added
      the msg_type as a class to the main HTML element, if msg_type is not
      None.
    * In addition, it sets the ``HX-Retarget`` header to ``.msg-flash`` which
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
        msg_type: Default to None, but if supplied, it can be any name as long
            as there is CSS in the form of ``.msg-flash:has(.{msg_type})`` to
            format the message for this type. If no CSS exists for the type,
            then the default, neutral formatting will be used.
    """
    # Classes to add to the main element.
    classes = [msg_type] if msg_type else []

    # Generate the output HTML
    if isinstance(msg, str):
        # A simple message goes into a div. For these we add a "message" class
        classes.append("message")
        html = f'<div class="{" ".join(classes)}">{msg}</div>'
    else:
        # Multiple messages goes into a list. For these we add a 'message-list'
        # class
        classes.append("message-list")
        html = '<ul class="{" ".join(classes)}">'
        html += "".join([f"<li>{m}</li>" for m in msg])
        html += "</ul>"

    # Create Microdot Response
    response = Response(body=html)
    # We will change the target for the response to the .msg-flash container,
    # overriding any default target from the original request.
    response.headers["HX-Retarget"] = ".msg-flash"

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
