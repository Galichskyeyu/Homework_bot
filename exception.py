class IsNot200Error(Exception):
    """Ответ сервера не 200."""


class ApiError(Exception):
    """Ошибка в запросе API."""


class JSONDecoderError(Exception):
    """Ошибка json."""