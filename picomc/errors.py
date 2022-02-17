class PicomcError(Exception):
    pass


class AuthenticationError(PicomcError):
    pass


class RefreshError(PicomcError):
    pass
