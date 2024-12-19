"""Custom exceptions for khard"""


class Cancelled(Exception):
    """An exception indicating that the user canceled some operation or
    some backend operation failed"""

    def __init__(self, message: str = "Canceled", code: int = 1) -> None:
        super().__init__(message)
        self.code = code


class AddressBookParseError(Exception):
    """Indicate an error while parsing data from an address book backend."""

    def __init__(self, filename: str, abook: str, reason: Exception) -> None:
        """Store the filename that caused the error."""
        super().__init__()
        self.filename = filename
        self.abook = abook
        self.reason = reason

    def __str__(self) -> str:
        return f"Error when parsing {self.filename} in address book {self.abook}: {self.reason}"


class AddressBookNameError(Exception):
    """Indicate an error with an address book name."""


class ConfigError(Exception):
    """Errors during config file parsing"""
