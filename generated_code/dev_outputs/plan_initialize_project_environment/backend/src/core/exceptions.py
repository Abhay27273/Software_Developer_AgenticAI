from fastapi import HTTPException, status
from typing import Union

class CustomException(HTTPException):
    """
    Base custom exception for the application.
    """
    def __init__(self, status_code: int, detail: str, headers: Union[dict, None] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class NotFoundException(CustomException):
    """
    Exception for resources not found.
    """
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class UnauthorizedException(CustomException):
    """
    Exception for unauthorized access.
    """
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})

class ForbiddenException(CustomException):
    """
    Exception for forbidden access.
    """
    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)