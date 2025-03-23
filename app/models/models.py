"""
Database peewee_ model definitions.

Note:
    Anywhere the term ``dis/charge`` is used, it is a short form to mean either
    ``charging`` or ``discharging``.

Attributes:
    db: The ``peeweePostgresqlDatabase`` connection using the `DB_HOST`,
        `DB_USER`, `DB_PASS` and `DB_NAME` `app.config` settings. This is set
        as the default DB connection in `BaseModel.Meta`

.. _peewee: http://docs.peewee-orm.com/en/latest/index.html
"""

import logging
from datetime import datetime

from peewee import (
    PostgresqlDatabase,
    Model,
    ForeignKeyField,
    IntegerField,
    CharField,
    TextField,
    SmallIntegerField,
    DateTimeField,
    DateField,
    FloatField,
    AutoField,
    DatabaseError,
)
from playhouse.postgres_ext import PostgresqlExtDatabase, JSONField

from app.config import (
    DB_HOST,
    DB_USER,
    DB_PASS,
    DB_NAME,
)

# Set up a local logger
logger = logging.getLogger(__name__)

# All these classes will have too few public methods, so
# @pylint: disable=too-few-public-methods

# The DB config
db = PostgresqlExtDatabase(
    DB_NAME, host=DB_HOST, user=DB_USER, password=DB_PASS, autoconnect=False
)


class BaseModel(Model):
    """
    Base database model.

    This model is the base for all other models, and specifies the database to
    use. All other models can then subclass this base.
    """

    class Meta:
        """
        Model config.

        Attributes:
            database: The default `db` connection.
        """

        database = db


class Battery(BaseModel):
    """
    Base battery entry for all available batteries.

    The base entry only contains the most import details per battery namely:

    * The Battery ID as marked on the battery itself
    * The last measured capacity in mAh
    * The last measurement date

    Linked to each entry are history entries via the `BatCapHistory` table
    which will give details for historical SoC measurements, including the last
    one that produced the current mAh capacity measurement.

    Attributes:
        id: Primary key auto incrementing ID
        created: Created timestamp
        modified: Modified timestamp - will indicate the last time the ``mah``
            field was updated.
        bat_id: The battery ID as received from the Battery Capacity Meter.
            This is also the same as `SoCEvent.bat_id`
        mah: The last measure capacity in mAh.
    """

    id = AutoField()
    created = DateTimeField(default=datetime.now, index=True)
    modified = DateTimeField(default=datetime.now, index=True)
    bat_id = CharField(unique=True, index=True, null=False, max_length=20)
    cap_date = DateField(null=False)
    mah = IntegerField(null=False)

    class Meta:
        """
        Model config.

        Attributes:
            table_name: Name of the table in the database.
        """

        table_name = "battery"

    def save(self, *args, **kwargs):
        """
        Auto-update modified timestamp on update.

        The alternative to this is to set a trigger on the DB, but this means
        we have to maintain this outside of the model definitions which is not
        the best approach in this instance.
        """
        if not self._pk:  # Only set modified if updating, not on insert
            self.modified = datetime.now()
        return super().save(*args, **kwargs)


class BatCapHistory(BaseModel):
    """
    State of Charge (SoC) history entry.

    These entries calculates a SoC or mAh capacity for a battery based on a
    group of SoC events received during a capacity measurement process. They
    record all measurement history for the `Battery`.

    Measuring the battery SoC is done on the Battery Capacity Meter (BCM) by
    starting a SoC measurement process. The SoC measurement flow is as follows:

    * First a UID for the process is created. This UID will be received with
        each `SoCEvent` from the BCM
    * The following cycles are then performed to measure the SoC:
        * Fully charge the battery to get to a known state
        * Fully discharge
        * Fully charge again
        * Repeat the discharge/charge cycles for as many times as the BCM is
            configured to do so.

    During the dis/charge cycle, regular `SoCEvent` messages are sent and
    recorded in the `SoCEvent` table.

    At the end of each dis/charge cycle, the event message contains details on
    the amount of charge, time, and the calculated mAh value for that cycle.

    Since charging and discharging uses different circuits to measure current
    flow (used to calculate charge), there may be differences in the mAh values
    measured for charging and discharging over the same time period. This can
    mostly be fixed by calibrating the calculation on the BCM, but may still be
    slightly out.

    In order to calculate the final mAh capacity for the battery, all mAh
    values for all final dis/charge events are averaged.

    If the BCM was not calibrated very well, there could be large differences
    between the charging and discharging mAh capacities. Regardless of
    calibration, there will still be differences in the amount of energy used
    for charging and discharging for the same battery due to battery age, etc.

    By taking the difference between the average of charge and discharge mAh
    calculated capacities as a percentage of the total averaged mAh capacity,
    we can get some indicator of how large the difference between charge and
    discharge energy is. This should be as close as possible to zero in a good
    battery and well calibrated BCM. This is represented by the `accuracy`
    value.

    Attributes:
        id: Primary key auto incrementing ID
        created: Created timestamp
        battery: FK to the `Battery` this entry links to.
        soc_uid: This is the UID from the Battery Capacity Meter used for the
            SoC measurement.

            This is the same as `SoCEvent.soc_uid` for the group of `SoCEvent`
            entries this history entry represents.
        mah: The final capacity in mAh.

            This is calculated from the final charge and discharge events in
            the group of `SoCEvent` records for this SoC measurement.
        accuracy: Accuracy of the `mah` value. See description above
        per_dch: Details specific to the charge and discharge events used to do
            the capacity measurements as a JSON structure.

            .. python::

                {      # Values specific to the dis/charge cycles
                    'ch': {       # Charge specific values
                        'mah_avg': int,   # Avg mAh for all charge cycles
                        'period': int,    # Avg period in secs for charge cycles
                        'shunt': float    # Shunt resistor in charge circuit
                    },
                    'dch': {
                        'mah_avg': int,   # Avg mAh for all discharge cycles
                        'period': int,    # Avg period in secs for discharge cycles
                        'shunt': float    # Shunt resistor in discharge circuit
                    }
                }

    """

    id = AutoField()
    created = DateTimeField(default=datetime.now, null=False, index=True)
    battery = ForeignKeyField(
        Battery, null=False, backref="cap_history", on_delete="CASCADE"
    )
    soc_uid = TextField(null=False, unique=True)
    mah = IntegerField(null=False)
    accuracy = IntegerField(null=False)
    num_events = IntegerField(null=False)
    # Will be something like {'ch': 145323, 'dch': 156345}
    per_dch = JSONField()

    class Meta:
        """
        Model config.

        Attributes:
            table_name: Name of the table in the database.
        """

        table_name = "bat_cap_history"


class SoCEvent(BaseModel):
    """
    State of Charge events received from the Battery Capacity meter.

    Attributes:
        id: Primary key auto incrementing ID
        created: Created timestamp
        bc_name: The Battery Controller (BC) used for this measurement.
        state: The battery or BC state for this event.

            These are strings like 'No Battery', 'Charging', 'Discharged',
            'Yanked', etc. They come from the Battery Controller State Machine
            in the Battery Capacity Meter codebase.

        bat_id: The unique battery ID selected for this battery.
        bat_v: The battery voltage at this event. May be ``Null`` for some event
            states.
        adc_v: Dis/charge monitor ADC value in **mV** for this event.

            This will only be set during a charging or discharging cycle, and
            will be ``Null`` for other `state` s.

        current: Dis/charge monitor **current** value in **mA** for this event.

            This will only be set during a charging or discharging cycle, and
            will be ``Null`` for other `state` s.

        charge: Dis/charge monitor **total charge** measured so far in **mC**
            for this event.

            This will only be set during a charging or discharging cycle, and
            will be ``Null`` for other `state` s.

            This is the charge in milliCoulomb measured so far.

        mah: Dis/charge monitor **accumulated charge** in **mAh** for this event.

            This will only be set during a charging or discharging cycle, and
            will be ``Null`` for other `state` s.

            This is the `charge` value multiplied by 3600 seconds to express
            the charge value relative to time.

        period: The total time this event has been in progress in seconds.
        shunt: The shunt resistor value for dis/charge events.

            This can help understand the `mah` or `current` differences between
            charge and discharge cycles. See also `BatCapHistory.accuracy`

        soc_state: The SoC measurement cycle state.

            These are strings from the SoC State Machine in the Battery
            Capacity Meter code base, and will only be populated during a SoC
            measurement cycle.

            There are strings like 'Initial Charge', 'Discharging',
            'Completed', 'Resting', 'Error', 'Charging', etc.

        soc_cycle: An integer for the current cycle in a SoC Measurement.
        soc_cycles: An integer for the total cycles to be completed in the SoC
            Measurement.
        soc_cycle_period: The period for the SoC measurement thus far in milliseconds.
        soc_uid: The UID used for all cycles in this SoC Measurement.
        bat_history: FK to link this event to a specific `BatCapHistory` event.
    """

    id = AutoField()
    created = DateTimeField(default=datetime.now, index=True)
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
    bat_history = ForeignKeyField(
        BatCapHistory, backref="soc_events", null=True, on_delete="SET NULL"
    )

    class Meta:
        """
        Model config.

        Attributes:
            table_name: Name of the table in the database.
        """

        table_name = "soc_event"
