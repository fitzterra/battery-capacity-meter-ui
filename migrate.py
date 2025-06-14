#!/usr/bin/env python
"""
Script to run any migrations.

Migrations are linked to versions, and the version is defined in the top level
VERSION file.

This version is available as ``config.VERSION`` after importing ``config`` from
``app``.

With the version in hand, we can then look for any migrations files in the
``migrations`` top level dir. Any version that requires a migration, will create
a dir inside this ``migrations`` dir matching its version number as ``vM.N.P``

Thus, if the current VERSION is 0.12.0 and we find a file as this path:
``migrations/v0.12.0/migration.py``, then we have a migration that can be run.

Note that for testing, the VERSION can also be set as an environment variable
which will override the ``config.VERSION`` value.
"""

import os
import sys
import logging
import importlib.util


from app.config import VERSION

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Override version from environment
VERSION = os.environ.get("VERSION", VERSION)
# Allow dry runs by looking for a DRY_RUN env var with any of the values in the
# list below. Any other values or no DR_RUN env var will not do a dry run.
DRY_RUN = os.environ.get("DRY_RUN", False) in ["true", "True", "1", "yes"]


def importFromPath(module_name, file_path):
    """
    Import a module given its name and file path.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    """
    Main entry point.
    """
    logger.info("Running migrations for version %s", VERSION)
    if DRY_RUN:
        logger.info(">>> Migrations DRY RUN <<<<")

    script = os.path.join("migrations", f"v{VERSION}", "migrate.py")

    # Is there a migration file?
    if not os.path.isfile(script):
        logger.info("No migration file found for this version. Quitting...")
        sys.exit(1)

    # Try to import the run function from this migration file
    try:
        migrate = importFromPath("migrate", script)
    except Exception as exc:
        logger.error("Unable to import migration file: %s", exc)
        sys.exit(1)

    # Now try the run() function
    try:
        migrate.run(logger, DRY_RUN)
    except Exception as exc:
        logger.error("Error running migration: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
