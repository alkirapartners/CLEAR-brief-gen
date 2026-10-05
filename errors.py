"""Errors whose message is safe to show to a partner."""

GENERIC_ERROR = "Something went wrong while writing this brief. Please try again."


class UserFacingError(Exception):
    status_code = 400


class BriefNotFound(UserFacingError):
    status_code = 404


class GenerationInFlight(UserFacingError):
    status_code = 409


class DailyLimitReached(UserFacingError):
    status_code = 429


class NotConfigured(UserFacingError):
    status_code = 503


class SaveFailed(UserFacingError):
    status_code = 502
