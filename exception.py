class ApiError(Exception):
    """Ошибка в запросе API."""


class IsNot200Error(Exception):
    """Ответ сервера не 200."""


class JSONDecoderError(Exception):
    """Ошибка JSON."""
