from rest_framework import status
from rest_framework.exceptions import APIException


class QuizGenerationFailed(APIException):
    """Generic 500 for external processing errors (details are only logged)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Quiz could not be generated. Please try again later.'
    default_code = 'quiz_generation_failed'
