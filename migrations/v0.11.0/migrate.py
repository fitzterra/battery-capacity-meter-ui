"""
Migration file for v0.11.0
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
    logger.info("Adding 'bc_name' field to 'bat_cap_history'...")

    db.connect()

    # Check if 'bc_name' already exists
    cursor = db.execute_sql(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'bat_cap_history'
          AND column_name = 'bc_name';
        """
    )
    if cursor.fetchone():
        logger.info(
            "\033[0;33m☉\033[0m Migration skipped: 'bc_name' column "
            "already exists on 'bat_cap_history'."
        )
        return

    try:
        # Run this in a transaction
        with db.atomic():
            logger.info("  Step 1: Adding nullable 'bc_name' column...")
            db.execute_sql("ALTER TABLE bat_cap_history ADD COLUMN bc_name TEXT;")

            logger.info(
                "  Step 2: Backfilling 'bc_name' values from earliest soc_event..."
            )
            db.execute_sql(
                """
                UPDATE bat_cap_history AS h
                SET bc_name = s.bc_name
                FROM (
                    SELECT DISTINCT ON (bat_history_id)
                        bat_history_id,
                        bc_name
                    FROM soc_event
                    WHERE bat_history_id IS NOT NULL
                    ORDER BY bat_history_id, created ASC
                ) AS s
                WHERE h.id = s.bat_history_id;
            """
            )

            logger.info("  Step 3: Verifying no NULLs remain...")
            nulls = db.execute_sql(
                "SELECT COUNT(*) FROM bat_cap_history WHERE bc_name IS NULL;"
            ).fetchone()[0]
            if nulls > 0:
                raise RuntimeError(
                    f"Cannot proceed: {nulls} rows still have NULL bc_name"
                )

            logger.info("  Step 4: Adding NOT NULL constraint and index...")
            db.execute_sql(
                "ALTER TABLE bat_cap_history ALTER COLUMN bc_name SET NOT NULL;"
            )
            db.execute_sql(
                "CREATE INDEX bat_cap_history_bc_name_idx ON bat_cap_history (bc_name);"
            )

            if dry_run:
                logger.info(
                    "  \033[0;32m☡\033[0m Dry run option set. Aborting all changes."
                )
                raise DryRunAbort()

    except DryRunAbort:
        logger.info("  \033[0;32m✔\033[0m Dry run complete. No changes were persisted.")

    logger.info("\033[0;32m✔\033[0m Migration complete.")
