class TokenError(Exception):
    """Occur with token errors."""
    pass


class APIError(Exception):
    """Errors according to API requests."""
    pass


class NotForSending(Exception):
    """Say not to update the timestamp."""
    pass
