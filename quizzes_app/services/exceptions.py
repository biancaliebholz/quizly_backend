class QuizGenerationError(Exception):
    """A quiz could not be generated (external service or invalid data)."""


class VideoTooLongError(QuizGenerationError):
    """The video exceeds the configured maximum length (invalid input)."""
