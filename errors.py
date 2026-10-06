"""Errors whose message is safe to show to a partner."""

GENERIC_ERROR = "Something went wrong while writing this brief. Please try again."


class UserFacingError(Exception):
    status_code = 400


class BriefNotFound(UserFacingError):
    status_code = 404


class GenerationInFlight(UserFacingError):
    status_code = 409


class ExportUnavailable(UserFacingError):
    """The brief exists, but not in a form this export can be made from."""

    status_code = 409


class ExportNotInstalled(UserFacingError):
    """This server cannot make the export at all: what it is built with did not load."""

    status_code = 503


class DailyLimitReached(UserFacingError):
    status_code = 429


class NotConfigured(UserFacingError):
    status_code = 503


class SaveFailed(UserFacingError):
    status_code = 502
