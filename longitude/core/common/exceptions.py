class LongitudeBaseException(Exception):
    pass


class LongitudeRetriesExceeded(LongitudeBaseException):
    pass


class LongitudeQueryCannotBeExecutedException(LongitudeBaseException):
    pass


class LongitudeWrongQueryException(LongitudeBaseException):
    pass


class LongitudeConfigError(LongitudeBaseException):
    pass