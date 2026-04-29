"""Shared exceptions for the automation pipeline."""


class GenerationError(RuntimeError):
    """Raised when the automation pipeline cannot continue."""
