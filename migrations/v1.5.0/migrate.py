"""
Migration file for v1.5.0
"""

from playhouse.migrate import PostgresqlMigrator, migrate
from app.models.models import db, Battery, BatteryPack, ForeignKeyField


class DryRunAbort(Exception):
    """Raised to abort a migration dry run."""


def run(logger, dry_run: bool = True):
    """
    Main entry point to be called from the migration manager

    Args:
        logger: A logging instance to use for local logging.
        dry_run: True if in dry-run mode, False otherwise.
    """
    logger.info("Running migration for version 1.5.0...")
    try:
        db.connect()

        logger.info("Creating 'BatteryPack' table...")
        # Does BatteryPack exist?
        if BatteryPack.table_exists():
            logger.info("   \033[0;33m⍻\033[0m Table already exists.")
        else:
            if not dry_run:
                BatteryPack.create_table()
            logger.info("   \033[0;32m✔\033[0m Table created.")

        # Now we add the FK to the pack to the battery table
        migrator = PostgresqlMigrator(db)

        # Define the new field
        pack_field = ForeignKeyField(
            BatteryPack,
            backref="cells",
            null=True,
            on_delete="RESTRICT",  # PostgreSQL RESTRICT behavior
            field=BatteryPack.id,  # ensures FK is on the pk of BatteryPack
        )

        logger.info("Adding `pack` FK to `Battery` table...")
        # First check if it does not already exist
        bat_cols = [col.name for col in db.get_columns(Battery._meta.table_name)]
        if "pack_id" in bat_cols:
            logger.info("   \033[0;33m⍻\033[0m FK already exists.")
        else:
            if not dry_run:
                migrate(
                    migrator.add_column("battery", "pack_id", pack_field),
                )
            logger.info("   \033[0;32m✔\033[0m FK added.")

        if dry_run:
            raise DryRunAbort()

    except DryRunAbort:
        logger.info("  \033[0;32m✔\033[0m Dry run complete. No changes were persisted.")

    logger.info("\033[0;32m✔\033[0m Migration complete.")
    db.close()
