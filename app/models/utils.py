"""
Utility functions focused on direct model and record interaction and
manipulation.
"""

import logging

from .models import (
    db,
    Battery,
    BatCapHistory,
    SoCEvent,
    DatabaseError,
)

# Set up a local logger
logger = logging.getLogger(__name__)


def measureSummary(soc_uid: str, bat_id: str, incl_end_events: bool = False) -> dict:
    """
    Generates a measurement summary for a specific `SoCEvent.soc_uid` and
    `SoCEvent.bat_id`.

    The summary is generated from the charge/discharge end events in the list
    of events.

    The events are also validated to ensure there is at least one
    discharge/charge cycle, including the initial charge cycle.

    Args:
        soc_uid: The `SoCEvent.soc_uid` for the measurement cycle.
        bat_id: The `SoCEvent.bat_id` this measurement UID is for.
        incl_end_events: If True, then a ``ModelSelect`` instance will be
            returned for only the end events (end of charge and discharge) used
            for the measure calculations.  This is useful for a UI that needs
            the summary and but also wants to show the end events.

    Returns:
        A dictionary as follows:

        .. python::

            {
                'success': bool,  # Indicates validation success or failure
                'msg': str,       # Error message if validation fails
                'mah_avg':  int,  # The calculated capacity average in mAh
                'accuracy': int,  # A percentage value indicating the accuracy
                                  # between charge and discharge mAh
                                  # measurements. See `BatCapHistory.accuracy`
                                  # for more details.
                'cycles': int,    # The number of cycles used for the capacity
                                  # measurement
                'date': datetime, # Date on which the measurement started.
                'num_events': int,# Total number of UID event recorded.
                'per_dch': {      # Values specific to the dis/charge cycles
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
                # Only if incl_end_events==True
                'end_evts': ModelSelect # Query result of end dis/charge events.
            }

        If ``success == False``, then only the ``msg`` value is reliable.
        Others may have values but they should not be used.
    """  # This is a busy method, so @pylint: disable=too-many-return-statements

    # Set up the structure we will return, presetting it as failed.
    res = {
        "success": False,
        "msg": "",
        "mah_avg": 0,
        "accuracy": 0,
        "cycles": 0,
        "date": None,
        "num_events": 0,
        "per_dch": {
            "ch": {
                "mah_avg": 0,
                "period": 0,
                "shunt": 0,
            },
            "dch": {
                "mah_avg": 0,
                "period": 0,
                "shunt": 0,
            },
        },
    }

    with db.connection_context():
        # Get all events for this UID and battery ID .
        events = SoCEvent.select().where(
            SoCEvent.soc_uid == soc_uid,
            SoCEvent.bat_id == bat_id,
        )
        # Get an idea of the number events we are dealing with
        num_events = events.count()

        # We need at least some events
        if not num_events:
            res["msg"] = (
                f"No events found for bat_id '{bat_id}' and soc_uid '{soc_uid}'."
            )
            logger.error(res["msg"])
            return res

        logger.info(
            "Found %s events for soc_uid %s and bat_id %s.",
            num_events,
            soc_uid,
            bat_id,
        )

        # Determine the measure date from the first entry
        # This is ok @pylint: disable=unsubscriptable-object
        res["date"] = events[0].created
        # pylint: enable=unsubscriptable-object

        # Also add the event count for the caller
        res["num_events"] = num_events

        # All bat_history IDs must be Null, i.e. not linked to a history
        # entry already.
        num_linked = events.where(SoCEvent.bat_history.is_null(False)).count()
        if num_linked == num_events:
            res["msg"] = (
                f"All events for soc_uid {soc_uid} are already marked as "
                f"capacity entries for Battery with ID {bat_id}"
            )
            logger.error(res["msg"])
            return res
        if num_linked != 0:
            res["msg"] = (
                f"Found {num_linked} out of {num_events} SoC Events for "
                f"soc_uid {soc_uid} already linked to history entries. "
                "Unable to set battery capacity for this soc_uid"
            )
            logger.error(res["msg"])
            return res

        # The capacity measurement is done by first charging the battery, then
        # one or more discharge/charge cycles. This means that if we look for
        # only events where state is one of 'Charged' or 'Discharged', ordered
        # by id ascending, and we ignore the first one (initial charge), we
        # should be left with at least 2 events, alternating between
        # charged/discharged.
        # These are the event states we are interested in, in the order they
        # should appear in the cycles
        end_states = ["Charged", "Discharged"]

        # Get all end dis/charge events
        end_events = events.where(SoCEvent.state.in_(end_states)).order_by(SoCEvent.id)
        if end_events.count() == 0:
            res["msg"] = (
                f"No end of dis/charge SoC events found for soc_uid {soc_uid}. "
                "Can not determine a capacity entry from this UID."
            )
            logger.error(res["msg"])
            return res

        # Do we include the end events in the result?
        if incl_end_events:
            res["end_evts"] = list(end_events.dicts())

        # Now we cycle through end events, validating each, and also
        # calculating the values we need.

        # The state_idx is an index into end_states we will use to check the
        # pattern of end events follow the expected charge/discharge pattern.
        state_idx = 0

        idx = 0  # Predefine it here so we are sure we can use it after the loop
        for idx, event in enumerate(end_events):
            # Check that we have the expected event state
            if event.state != end_states[state_idx]:
                res["msg"] = (
                    f"End dis/charge SoC event {idx} is state {event.state} while "
                    f"it was expected to be in state {end_states[state_idx]} for "
                    f"soc_uid {soc_uid}. The measurement events are not in the "
                    "expected order."
                )
                logger.error(res["msg"])
                return res
            # Advance the state index to the next state
            state_idx = 0 if state_idx else 1

            # We ignore the initial charge event
            if idx == 0:
                continue

            # Increment the cycle count. We can probably pick this up from the
            # 'soc_cycles' field in one of the events, but to be sure, we also
            # calculate it. We only count the charge end events.
            res["cycles"] += 1 if event.state == "Charged" else 0

            # Accumulate for the correct charge
            # TODO: Should probably validate that these are valid ints
            res["per_dch"]["ch" if event.state == "Charged" else "dch"][
                "mah_avg"
            ] += event.mah
            res["per_dch"]["ch" if event.state == "Charged" else "dch"][
                "period"
            ] += event.period
            # Record the shunt values
            res["per_dch"]["ch" if event.state == "Charged" else "dch"][
                "shunt"
            ] = event.shunt

        # When we get here, idx starting from 0, should the total number of end
        # events (we exclude the 0th event which is the initial charge event).
        # We require these events to be an even value >= 2
        if idx < 2 or idx % 2 != 0:
            res["msg"] = (
                "Expected to have an odd number (> 3) completed dis/charge "
                f"events but seeing {idx+1} such events. This seems to be a "
                "malformed capacity measurement."
            )
            logger.error(res["msg"])
            return res

        # All looking good. Calculate the final averages
        for avg in res["per_dch"].values():
            # The accumulated values per dis/charge average needs to be divided
            # by the number of the such events, which would be half of idx (idx
            # starts from 0 and we disregard the first charge event, so its
            # value will be the remaining dis/charge events).
            avg["mah_avg"] = avg["mah_avg"] / (idx // 2)
            res["mah_avg"] += avg["mah_avg"]
            avg["period"] = avg["period"] / (idx // 2)

        # The final average needs to be calculated as half of the sum of the two
        # dis/charge averages we accumulated above.
        res["mah_avg"] = round(res["mah_avg"] / 2)

        # The accuracy of the mAh average is calculated as the percentage of the
        # difference between the dis/charge mAh averages, subtracted from the final
        # average, to the final average:
        #
        #            mah_avg - abs(dch_mha_avg - ch_ha_avg)
        # accuracy = --------------------------------------  X 100
        #                          mah_avg
        per_dch = res["per_dch"]
        res["accuracy"] = round(
            (res["mah_avg"] - abs(per_dch["dch"]["mah_avg"] - per_dch["ch"]["mah_avg"]))
            * 100
            // res["mah_avg"]
        )

        res["success"] = True
        return res


def setCapacityFromSocUID(soc_uid: str, bat_id: str) -> dict:
    """
    Record a series of `SoCEvent` as a `Battery` capacity measurement.

    See `BatCapHistory` for more details on how battery capacity measurements
    are done through a series of `SoCEvent` received during the measurements
    cycles.

    This function will examine the set of `SoCEvent` s with the given
    ``soc_uid`` and ``bat_id`` for the end of charge and discharge events, and
    from there determine the capacity for the battery for that measurement
    cycle.

    Once it is able to determine the capacity, it will create a new `Battery`
    entry if one does not already exists, and then create a new `BatCapHistory`
    entry linked to the battery, and lastly link all the `SoCEvent` entries to
    the new `BatCapHistory` entry.

    This function will log any errors and return a dictionary with details on
    success or error with UI surfaceable error/success messages.

    Args:
        soc_uid: The UID used by the Battery Capacity Meter for this
            measurement cycle.

    Returns:
        A dict as follows:

        .. python::

            {
                'success': bool,  # Indicates success of failure
                'msg': str        # An error message explaining the success value
            }
    """
    # Preset the return dict to failure
    res = {"success": False, "msg": "Unknown error."}

    # Generate a measure summary and event validation for this uid and bat_id
    v_res = measureSummary(soc_uid, bat_id)

    if not v_res["success"]:
        res["msg"] = v_res["msg"]
        return res

    ### Capacity Entries Creation ###

    # Now we have everything we need to create the history and battery
    # entry if needed. But we do this in a transaction to ensure we either
    # get everything done, or nothing.
    try:
        with db.atomic():

            # Get the Battery entry for this battery, or create it with our
            # calculated values if it does not exist
            bat, created = Battery.get_or_create(
                bat_id=bat_id,
                defaults={"mah": v_res["mah_avg"], "cap_date": v_res["date"]},
            )
            if not created and v_res["date"].date() > bat.cap_date:
                # This battery exists, and the new capture date is greater than
                # the last capture date, so let's update to the new values
                # NOTE: v_res["date"] id a dateime object, so we need to
                #   convert it to a date object in order to do the comparison
                #   with cap_date which is a date type object.
                bat.mah = v_res["mah_avg"]
                bat.cap_date = v_res["date"]
                bat.save()

            # Now we can create a new history entry
            bat_cap_hist = BatCapHistory.create(
                battery=bat,
                soc_uid=soc_uid,
                mah=v_res["mah_avg"],
                accuracy=v_res["accuracy"],
                num_events=v_res["num_events"],
                per_dch=v_res["per_dch"],
            )

            # And lastly, we update all the event entries for this soc_uid to
            # point to the bat_cap_hist instance
            SoCEvent.update(bat_history=bat_cap_hist).where(
                SoCEvent.soc_uid == soc_uid
            ).execute()

    except DatabaseError as exc:
        logger.error(
            "Error setting soc_ui %s as a capacity entry. Error: %s", soc_uid, exc
        )
        res["msg"] = (
            "An error occurred setting this UID as a capacity "
            "entry. See the log for more info"
        )
        return res

    res["success"] = True
    res["msg"] = (
        f"New capacity measure added for Battery with ID '{bat_id}' "
        f"from SoC UID '{soc_uid}'"
    )

    return res
