"""Raised when a tab's layout no longer matches what its parser expects."""


class ParseError(Exception):
    """A tab's layout no longer matches what its parser expects."""

    def __init__(self, tab, message):
        super().__init__(f"{tab}: {message}")
        self.tab = tab
