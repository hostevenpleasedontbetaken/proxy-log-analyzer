"""Problems that reject the whole file (the API turns these into a 4xx with this code)."""


class ParseFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # stable identifier, e.g. "not_zscaler_web"
        self.message = message
