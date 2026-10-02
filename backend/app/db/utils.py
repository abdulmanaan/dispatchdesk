"""Small SQL helpers."""


def like_pattern(term: str) -> str:
    """Build a ``%term%`` pattern for ILIKE with ``escape="\\"``.

    ``%`` and ``_`` in the user's input are escaped so they match literally.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
