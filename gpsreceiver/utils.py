class InvariantError(Exception):
    """An exception raised when an invariant condition is violated."""

    pass


def invariant(condition: bool, message: str = "") -> None:
    """Checks an invariant condition.

    This is similar to the built-in ``assert`` keyword, but remains present even
    if the code is run with the ``-O`` option and ``__debug__`` is ``False``.
    """
    if not condition:
        raise InvariantError(message)
