"""
Migration file for v1.13.0
"""

from app.models.models import db, InternalResistance


def run(logger, dry_run: bool = True):
    """
    Main entry point to be called from the migration manager


    Args:
        logger: A logging instance to use for local logging.
        dry_run: True if in dry-run mode, False otherwise.
    """
    logger.info("Going to create InternalResistance table...")

    db.connect()
    if not dry_run:
        InternalResistance.create_table()
    else:
        logger.info("DRY RUN: Not creating table ...")

    logger.info("InternalResistance table created.")

    logger.info("\033[0;32m✔\033[0m Migration complete.")
    db.close()
