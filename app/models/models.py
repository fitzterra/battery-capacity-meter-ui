"""
Database peewee_ model definitions.

Note:
    Anywhere the term ``dis/charge`` is used, it is a short form to mean either
    ``charging`` or ``discharging``.

Attributes:
    db: The ``peeweePostgresqlDatabase`` connection using the `DB_HOST`,
        `DB_USER`, `DB_PASS` and `DB_NAME` `app.config` settings. This is set
        as the default DB connection in `BaseModel.Meta`
    logger: Local module logger

.. image:: img/ERD.png
    :width: 100%

.. _peewee: http://docs.peewee-orm.com/en/latest/index.html
"""

import logging
from datetime import datetime

# DatabaseError is imported from here by data.py, so @pylint: disable=unused-import
from peewee import (
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
    fn,
    SQL,
)

# pylint: enable=unused-import

from playhouse.postgres_ext import PostgresqlExtDatabase, JSONField
from app.utils import datesToStrings

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

    This model is the base for all other models.
    It only sets the `Meta.database` to `db` which then binds all derived
    models to this DB connection.

    All other models can then subclass this base.
    """

    class Meta:
        """
        Model config for the base model class.

        Attributes:
            database: The default `db` to bind all derived model to.
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
    which will give details for historical SoC measurements.

    The capacity and capture date values shown here are from the most recent
    `BatCapHistory` entry for this battery, thus representing the last known and
    tested capacity.

    Attributes:
        id: Primary key auto incrementing ID
        created: Created timestamp
        modified: Modified timestamp - will indicate the last time the ``mah``
            field was updated. Note that this is not the same as the `cap_date`.
        bat_id: The battery ID as received from the Battery Capacity Meter.
            This is also the same as `SoCEvent.bat_id`
        cap_date: The date the measure was made on. This is the
            `BatCapHistory.cap_date` value for the most recent history entry.
        mah: The last measure capacity in mAh. This is the
             `BatCapHistory.mah` value for the most recent history entry.
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
    Battery capacity history entry.

    Each entry records one capacity measurement cycle for a `Battery`. A
    `Battery` may have more than capacity measurement in this history table.

    Measuring the battery capacity is done by the **Battery Capacity Meter**
    (BCM) by starting a SoC measurement process. The SoC measurement flow is as
    follows:

    * First a UID for the process is created. This UID will be received with
        each `SoCEvent` from the BCM
    * The following cycles are then performed to measure the capacity:
        * Fully charge the battery to get to a known state
        * Fully discharge
        * Fully charge again
        * Repeat the discharge/charge cycles for as many times as the BCM is
            configured to do so.

    During the dis/charge cycle, regular `SoCEvent` messages are sent and
    recorded in the `SoCEvent` table.

    At the end of each dis/charge cycle, the event message contains details on
    the amount of charge, time, and the calculated mAh capacity for that cycle.

    Since charging and discharging uses different circuits to measure current
    flow (used to calculate charge), there may be differences in the mAh values
    measured for charging and discharging over the same time period. This can
    mostly be fixed by calibrating the calculation on the BCM, but may still
    differ slightly between dis/charge cycles.

    In order to calculate the final mAh capacity for the battery, all mAh
    values for all final dis/charge events are averaged.

    If the BCM was not calibrated very well, there could be large differences
    between the charging and discharging mAh capacities. Regardless of
    calibration, there will still be differences in the amount of energy used
    for charging and discharging for the same battery due to battery age, etc.

    By taking the difference between the average of charge and discharge mAh
    calculated capacities as a percentage of the total averaged mAh capacity,
    we can get some indicator of how large the difference between charge and
    discharge energy is. This is represented by the `accuracy` value as a
    percentage of accuracy between charge and discharge capacities.

    Attributes:
        id: Primary key auto incrementing ID
        created: Created timestamp
        battery: FK to the `Battery` this entry links to.
        soc_uid: This is the UID from the Battery Capacity Meter used for the
            SoC measurement.

            This is the same as `SoCEvent.soc_uid` for the group of `SoCEvent`
            entries this history entry represents.
        cap_date: Date on which the capacity measurement was started.

            These measurements may take quite long and can cross day
            boundaries. This date will be the date for the first event in the
            capacity measurement cycle events.
        mah: The final capacity in mAh.

            This is calculated from the final charge and discharge events in
            the group of `SoCEvent` records for this SoC measurement.
        accuracy: Accuracy of the `mah` value. See description above.
        num_events: The total number of `SoCEvent` entries for this capacity
            measurement.
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
    cap_date = DateTimeField(null=False)
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

    def cycleSummary(self, raw_dates=False) -> list[dict]:
        """
        Returns a summary of all the dis/charge cycles that occurred for this
        measurement.

        This summary would look like this::

            +----------------------------+------------+-------------+----------------+-------------+
            | timestamp                  | bat_id     | state       | soc_state      | event_count |
            |----------------------------+------------+-------------+----------------+-------------|
            | 2025-04-12 12:56:35.359294 | 2025012801 | Charging    | Initial Charge | 1222        |
            | 2025-04-12 14:39:41.916675 | 2025012801 | Charged     | Resting        | 1           |
            | 2025-04-12 14:44:42.054048 | 2025012801 | Discharging | Discharging    | 881         |
            | 2025-04-12 15:59:01.900153 | 2025012801 | Discharged  | Resting        | 1           |
            | 2025-04-12 16:02:01.907227 | 2025012801 | Charging    | Charging       | 1871        |
            | 2025-04-12 18:40:01.775469 | 2025012801 | Charged     | Charging       | 1           |
            | 2025-04-12 18:45:02.192154 | 2025012801 | Discharging | Discharging    | 901         |
            | 2025-04-12 20:01:04.091049 | 2025012801 | Discharged  | Discharging    | 1           |
            | 2025-04-12 20:04:04.354959 | 2025012801 | Charging    | Charging       | 1873        |
            | 2025-04-12 22:42:09.303524 | 2025012801 | Charged     | Completed      | 1           |
            +----------------------------+------------+-------------+----------------+-------------+

        Args:
            raw_dates: If True, dates will be returned as datetime objects. If
                False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
                strings. See `datesToStrings`

        Returns:
            A list of dictionaries like:

            .. python::

                {
                    'timestamp': str | datetime
                    'bat_id': str,
                    'state': str,
                    'soc_state': str,
                    'event_count': int
                }
        """  # pylint: disable=line-too-long

        with db.connection_context():
            # Aliases for clarity
            created = SoCEvent.created
            bat_id = SoCEvent.bat_id
            state = SoCEvent.state
            soc_state = SoCEvent.soc_state
            bat_history = SoCEvent.bat_history

            # Window of row numbers over bat_id
            row_number_bat = fn.ROW_NUMBER().over(
                partition_by=[bat_id], order_by=[created]
            )

            # Window of row numbers over bat_id and state combo
            row_number_bat_state = fn.ROW_NUMBER().over(
                partition_by=[bat_id, state], order_by=[created]
            )

            # CTE (Common Table Expression) to select all events adding a
            # grouping value based row numbers defined above.
            cycle_events = (
                SoCEvent.select(
                    created,
                    bat_id,
                    state,
                    soc_state,
                    (row_number_bat - row_number_bat_state).alias("grp"),
                )
                .where(bat_history == self.id)
                .cte("cycle_events")  # Define the CTE name
            )

            # Main query using the CTE
            query = (
                SoCEvent.select(
                    fn.MIN(cycle_events.c.created).alias("timestamp"),
                    cycle_events.c.bat_id,
                    cycle_events.c.state,
                    cycle_events.c.soc_state,
                    fn.COUNT("*").alias("event_count"),
                )
                .from_(cycle_events)  # Reference the CTE
                .group_by(
                    cycle_events.c.bat_id,
                    cycle_events.c.state,
                    cycle_events.c.soc_state,
                    cycle_events.c.grp,
                )
                .order_by(SQL("timestamp"))
                .with_cte(cycle_events)  # Reference the CTE
            )

            # We need to convert the datetime objects to date time strings for each
            # entry if raw_dates is True
            res = [row if raw_dates else datesToStrings(row) for row in query.dicts()]
            return res

    def measureSummary(self, raw_dates=False) -> list[dict]:
        """
        Returns a summary of all the measurement cycle dis/charge events.

        The summary would look like this::

            +---------------------+---------+------------+------------+-------+------+--------+-----------+-------+-----------+
            | timestamp           | bc_name | state      | bat_id     | bat_v | mah  | period | soc_state | cycle | plot_ind  |
            |---------------------+---------+------------+------------+-------+------+--------+-----------+-------+-----------|
            | 2025-02-04 16:57:24 | BC0     | Charged    | 2025020401 | 4179  | 198  | 2676   | Resting   | 1/2   |    c0     |
            | 2025-02-04 21:28:29 | BC0     | Discharged | 2025020401 | 2721  | 1888 | 15960  | Resting   | 1/2   |    d1     |
            | 2025-02-05 02:33:35 | BC0     | Charged    | 2025020401 | 4176  | 2851 | 18024  | Resting   | 2/2   |    c1     |
            | 2025-02-05 07:03:43 | BC0     | Discharged | 2025020401 | 2745  | 1877 | 15903  | Resting   | 2/2   |    d2     |
            | 2025-02-05 11:37:05 | BC0     | Charged    | 2025020401 | 4190  | 2579 | 16217  | Completed | 2/2   |    c2     |
            +---------------------+---------+------------+------------+-------+------+--------+-----------+-------+-----------+

        The ``plot_ind`` field can be used to generate plot data for a specific
        dis/charge cycle. This is used as argument to the `plotData` method.

        Args:
            raw_dates: If True, dates will be returned as datetime objects. If
                False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
                strings. See `datesToStrings`

        Returns:
            A list of dictionaries like:

            .. python::

                {
                    'timestamp': str | datetime
                    'bc_name': str,
                    'state': str,
                    'bat_id': str,
                    'bat_v': int,  # milliVolt
                    'mah': int,    # milliAmp
                    'period': int, # Cycle time in seconds
                    'soc_state': str,
                    'cycle': str,
                    'plot_ind': The plot indicator for calling `plotData`
                }
        """  # pylint: disable=line-too-long

        with db.connection_context():
            query = (
                SoCEvent.select(
                    SoCEvent.created.alias("timestamp"),
                    SoCEvent.bc_name,
                    SoCEvent.state,
                    SoCEvent.bat_id,
                    SoCEvent.bat_v,
                    SoCEvent.mah,
                    SoCEvent.period,
                    SoCEvent.soc_state,
                    # This is in fact callable, @pylint: disable=not-callable
                    fn.CONCAT(SoCEvent.soc_cycle, "/", SoCEvent.soc_cycles).alias(
                        "cycle"
                    ),
                )
                .where(
                    SoCEvent.bat_history == self.id,
                    SoCEvent.state.in_(["Charged", "Discharged"]),
                )
                .order_by(SoCEvent.id)
            )

            # We need to convert the datetime objects to date time strings for each
            # entry if raw_dates is True
            res = [row if raw_dates else datesToStrings(row) for row in query.dicts()]

            # TODO:
            # Fix this in the firmware and anywhere else it needs to be fixed.
            # Currently the soc_cycle value for the Dis/Charged states are a
            # bit wonky, and is one cycle off for the charge cycles. For
            # example, the cycle values in the table in the doc string should
            # be:
            #      state      |cycle             cycle           plot_ind
            #      -----------+-----   and not   ----- to give:  --------
            #      Charged    |0/2               1/2               c0
            #      Discharged |1/2               1/2               d1
            #      Charged    |1/2               2/2               c1
            #      Discharged |2/2               2/2               d2
            #      Charged    |2/2               2/2               c2
            #
            # With these fixed cycle values we can infer a plot indicator as in
            # the last column to help us find the soc_events that should be
            # used to plot the measure curves for each dis/charge cycle.
            #
            # The plot_ind will then be used to select soc events as follows:
            #
            #  plot_ind  SoCEvent.state  SoCEvent.soc_cycle
            #  c0        "Charging"          0
            #  d1        "Discharging"       1
            #  c1        "Charging"          1
            #  d2        "Discharging"       2
            #  c2        "Charging"          2
            #
            # We will manually add this plot indicator now, by cycling through
            # the 'c' and 'd' for each row, and incrementing the soc cycle
            # counter on every even entry.
            cd = "c"  # Start with Charging
            cycle = 0  # Start the 0th cycle for the initial charge
            for idx, row in enumerate(res):
                row["plot_ind"] = f"{cd}{cycle}"
                # The cd value alternates on every row
                cd = "d" if cd == "c" else "c"
                # The cycle increments only on even rows
                if idx % 2 == 0:
                    cycle += 1

            return res

    def plotData(self, plot_ind: str, max_points: int | None = 200) -> list[dict]:
        """
        Returns the data points for plotting the cycle graphs for this history
        entry and the given plot indicator.

        The plot indicator is used to identify a specific cycle as::

            state      |cycle|plot_ind
            -----------+-----+--------
            Charged    |0/2  |  c0
            Discharged |1/2  |  d1
            Charged    |1/2  |  c1
            Discharged |2/2  |  d2
            Charged    |2/2  |  c2

        The first character is either ``c`` or ``d`` and indicates the ``Charging``
        or ``Discharging`` events that lead up to the final completed ``Charged``
        or ``Discharged`` state.

        The second character is an integer that indicates the
        `SoCEvent.soc_cycle` for the events.

        The ``plot_ind`` will be returned for each cycle by the
        `measureSummary` method.

        A list of dictionaries with measurement values for a given timestamp
        will be returned. Each entry in the list will look like:

        .. python::

            {
                'timestamp': 1738461765428.51, # Unix timestamp in millisecs
                'bat_v': 4215,                 # Battery voltage in mV
                'current': 212,                # Current in mA
                'charge': 9185919,             # Charge in mC
                'mah': 2552                    # Capacity in mAh
            }

        No validation on the input is done, so if it breaks you keep all the
        pieces :-)

        Args:
            plot_ind: Two character string as above.
            max_points: Optionally returns a smaller subset of data points.

                Each measurement cycle may consist of thousands of events that
                will be used to generate the plot data. Since this is not
                always practical in a web app or similar, this setting allows
                for a smaller sample of points to be returned

                If None, all points are returned. If an integer, some points in
                the plot set will be dropped to only return as many points as
                requested. Note that there may be a few more or less points
                than this value indicates.

        Returns:
            A list of dictionaries as described above.
        """
        # Convert the first character in plot_ind to the Charging or
        # Discharging status string by looking it up in the table below
        st = {"c": "Charging", "d": "Discharging"}[plot_ind[0]]

        # The cycle number as integer
        cn = int(plot_ind[1])

        with db.connection_context():
            query = (
                SoCEvent.select(
                    # Converts the created date to Unix timestamp in
                    # milliseconds so we can use it directly as a 'time' scale
                    # type in Chart.JS
                    (db.extract_date("epoch", SoCEvent.created) * 1000).alias(
                        "timestamp"
                    ),
                    SoCEvent.bat_v,
                    SoCEvent.current,
                    SoCEvent.charge,
                    # The mAh value may still be NULL for the first few
                    # measurements, so we let the DB return these as 0
                    # fn.COALESCE(SoCEvent.mah, 0).alias('mah'),
                    SoCEvent.mah,
                )
                .where(
                    SoCEvent.bat_history == self.id,
                    SoCEvent.state == st,
                    SoCEvent.soc_cycle == cn,
                )
                .order_by(SoCEvent.created)
            )

            # Limit the number of points to return?
            if max_points:
                num_points = query.count()
                if num_points <= max_points:
                    step = 1
                else:
                    step = num_points // max_points

                plot_data = list(query.dicts())[::step]
            else:
                plot_data = list(query.dicts())

        return plot_data


class SoCEvent(BaseModel):
    """
    Charge/Discharge measurement events received from the Battery Capacity
    Meter (BCM).

    This table will be populated by some process that listens for the MQTT
    events published by the BCM, and then writing it to this table. This could
    be a NodeRed_ flow or something similar.

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
            This field will be  ``NULL`` unless this event is linked to a
            `BatCapHistory` entry.

    .. _NodeRed: https://nodered.org/docs
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
