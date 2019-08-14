from enum import Enum


def is_enum(obj):
    """Determines whether the object is an enum.Enum."""

    if obj is None:
        return True

    try:
        return issubclass(obj.__class__, Enum)
    except TypeError:
        return False
