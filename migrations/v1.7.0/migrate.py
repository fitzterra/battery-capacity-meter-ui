"""
Migration file for v1.7.0

Update the `Battery.pack` FK constraint to set this FK to NULL if the pack is
deleted.
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
    # The FK contraint name we will update.
    fk_const = "battery_pack_id_fkey"

    logger.info(
        "Running migration for version 1.7.0...%s", " (DRY RUN)" if dry_run else ""
    )
    try:
        with db.atomic():

            logger.info("Dropping Battery FK constraint: %s", fk_const)

            db.execute_sql(
                f"""
                ALTER TABLE battery
                DROP CONSTRAINT {fk_const};
                """
            )

            logger.info(
                "Adding new Battery FK constraint: %s - "
                "setting to NULL if battery pack is deleted.",
                fk_const,
            )
            db.execute_sql(
                f"""
                ALTER TABLE battery
                ADD CONSTRAINT {fk_const}
                FOREIGN KEY (pack_id)
                REFERENCES battery_pack(id)
                ON DELETE SET NULL;
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
