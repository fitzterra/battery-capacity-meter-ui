"""
This module contains any general utility functions used across the app.
"""

from datetime import datetime, date


def datesToStrings(item: dict | tuple) -> dict | tuple:
    """
    Converts any ``datetime`` or ``date`` elements in the input ``tuple`` or
    ``dict`` to string representations.

    This is useful for returning query results that needs to be converted to
    JSON on output, for example.

    For ``tuples``, each element is tested for being an instance of
    ``datetime`` or ``date``, and for ``dicts`` each value is tested.

    For ``datetime`` instances, the value is converted to a string in the
    format: ``"YYYY-MM-DD HH:MM:SS"``

    For ``date`` instances, the value is converted to a string in the format:
    ``"YYY-MM-DD"``

    Args:
        item: A dict or tuple with any number of fields, of which one or more
            may be ``datetime`` or ``date`` type objects.

    Returns:
        If ``item`` is a tuple, a new tuple with the same elements as the
        input, except for all ``datetime``/``date`` type elements converted to
        strings as noted above.

        If ``item`` is a dict, any field values that match are converted, and
        the dict is returned.
    """

    def convIfDate(v):
        """
        Converts v to string representation of a datetime or date item, else it
        just returs v.
        """
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, date):
            return v.strftime("%Y-%m-%d")

        return v

    if isinstance(item, tuple):
        return tuple(convIfDate(f) for f in item)

    # Assume it's a dict
    for k, v in item.items():
        item[k] = convIfDate(v)

    return item
