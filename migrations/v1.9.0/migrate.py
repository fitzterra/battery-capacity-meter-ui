"""
Migration file for v1.9.0

Add fields ``dimension`` and ``placement`` the `Battery` table.
"""

from app.models.models import db


class DryRunAbort(Exception):
    """Raised to abort a migration dry run."""


def run(logger, dry_run: bool = True):
    """
    Main entry point to be called from the migration manager

    Args:
        logger: A logging instance to use for local logging.
        dry_run: True if in dry-run mode, False otherwise.
    """
    logger.info(
        "Running migration for version 1.9.0...%s", " (DRY RUN)" if dry_run else ""
    )
    try:
        with db.atomic():

            logger.info("Adding 'dimension' and 'placement' fields to Battery...")

            db.execute_sql(
                """
                ALTER TABLE battery ADD COLUMN dimension TEXT DEFAULT NULL;
                ALTER TABLE battery ADD COLUMN placement TEXT DEFAULT NULL;
                """
            )

            # If it's a dry-run we raise the abort exception here which will
            # roll the changes back.
            if dry_run:
                raise DryRunAbort()

    except DryRunAbort:
        logger.info("  \033[0;32m✔\033[0m Dry run complete. No changes were persisted.")

    logger.info("\033[0;32m✔\033[0m Migration complete.")
    db.close()
