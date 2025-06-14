"""
Migration file for v0.10.0
"""

from app.models.models import db, BatteryImage


def run(logger, dry_run: bool = True):
    """
    Main entry point to be called from the migration manager


    Args:
        logger: A logging instance to use for local logging.
        dry_run: True if in dry-run mode, False otherwise.
    """
    logger.info("Going to create BatteryImage table...")

    db.connect()
    if not dry_run:
        BatteryImage.create_table()
    else:
        logger.info("DRY RUN: Not creating table ...")

    logger.info("BatteryImage table created.")
