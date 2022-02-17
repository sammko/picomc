class PicomcError(Exception):
    pass


class AuthenticationError(PicomcError):
    pass


class RefreshError(PicomcError):
    pass


class ValidationError(PicomcError):
    pass
