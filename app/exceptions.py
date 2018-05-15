class AutoscalerException(Exception):
    pass


class CannotLoadConfig(AutoscalerException):
    pass


class CannotLoadApp(AutoscalerException):
    pass
