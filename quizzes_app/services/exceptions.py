class QuizGenerationError(Exception):
    """A quiz could not be generated (external service or invalid data)."""


class InvalidVideoError(QuizGenerationError):
    """The video itself cannot be used for a quiz (client error, HTTP 400)."""


class VideoTooLongError(InvalidVideoError):
    """The video exceeds the configured maximum length."""


class TranscriptTooShortError(InvalidVideoError):
    """The transcript contains too little speech for a meaningful quiz."""
