"""
API custom exceptions.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


class ApiError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(ApiError, self).__init__(code, message)


class BadRequestError(ApiError):
    pass


class ForbiddenError(ApiError):
    pass


class NotAcceptableError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class UnauthorizedError(ApiError):
    pass


class UnsatisfiableRangeError(ApiError):
    pass
