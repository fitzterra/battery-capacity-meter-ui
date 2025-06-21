#!/usr/bin/env python
#
# Script to compile all templates

import sys
import shutil
import logging
from pathlib import Path
from microdot.utemplate import Template
from app import config


def comp(logger: logging.Logger, dry_run: bool = False):
    """
    Compiles all templates.

    This function will delete all compiled templates in the templates dir, as
    well as the ``__pycache__`` dir, and then recompile all templates.

    Args:
        logger: A logger instance for output logging.
        dry_run: For now this is ignored, but may be used in future.

    Returns:
        True on success, False on error
    """

    tmpl_dir = Path(config.TMPL_DIR)
    if not tmpl_dir.is_dir():
        logger.info("Templates dir [%s] is not a directory.)", config.TMPL_DIR)
        return False

    # Set the base for our templates
    Template.initialize(config.TMPL_DIR)

    # First delete all python modules
    for mod in tmpl_dir.glob("*_html.py"):
        logger.info("Deleting: %s", mod.name)
        mod.unlink()

    # Also delete the cache dir if it exists
    cache = tmpl_dir / "__pycache__"
    if cache.is_dir():
        logger.info("Deleting cache dir: %s", cache)
        # Need to use shutil here to remove the full tree
        shutil.rmtree(cache)

    # Run through all the HTML files in the dir
    for tmpl in tmpl_dir.glob("*.html"):
        # Drop the full path name, leaving only the template name
        tmpl = tmpl.name
        logger.info("Compiling %s ...", tmpl)
        try:
            Template(tmpl).render({})
        except Exception:
            # We ignore all errors since the templates will need args in the
            # render call, but we do not supply that. The render call will
            # compile the template, and that is all we are interested in now.
            pass

    return True


# This can also be run a script from the makefile for local template
# compilation
if __name__ == "__main__":
    if comp(logging):
        sys.exit(0)
    else:
        sys.exit(1)
