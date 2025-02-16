"""
Database model definitions
"""

from peewee import (
    PostgresqlDatabase,
    Model,
    IntegerField,
    CharField,
    TextField,
    SmallIntegerField,
    DateTimeField,
    FloatField,
    AutoField,
    SQL,
)
from app.config import (
    DB_HOST,
    DB_USER,
    DB_PASS,
    DB_NAME,
)

# All these classes will have too few public methods, so
# @pylint: disable=too-few-public-methods

# The DB condig
database = PostgresqlDatabase(DB_NAME, host=DB_HOST, user=DB_USER, password=DB_PASS)


class BaseModel(Model):
    """
    Base database model.

    This model is the base for all other models, and specifies the database to
    use. All other models can then subclass this base.
    """

    class Meta:
        """
        Model config
        """

        database = database


class BatCap(BaseModel):
    """
    Battery Capacity Metrics.
    """

    id = AutoField()
    created = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")], index=True)
    bc_name = TextField(index=True)
    state = TextField(index=True)
    bat_id = CharField(index=True, null=True, max_length=20)
    bat_v = IntegerField(null=True)
    adc_v = IntegerField(null=True)
    current = IntegerField(null=True)
    charge = IntegerField(null=True)
    mah = IntegerField(null=True)
    period = IntegerField(null=True)
    shunt = FloatField(null=True)
    soc_state = TextField(null=True)
    soc_cycle = SmallIntegerField(null=True)
    soc_cycles = SmallIntegerField(null=True)
    soc_cycle_period = IntegerField(null=True)
    soc_uid = TextField(index=True, null=True)

    class Meta:
        """
        Model config
        """

        table_name = "bat_cap"
