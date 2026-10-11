from django.core.exceptions import ValidationError

OPTION_COUNT = 4
QUESTION_COUNT = 10
OPTIONS_ERROR = (
    f'Provide exactly {OPTION_COUNT} distinct, non-empty text options.'
)
ANSWER_ERROR = 'The answer must be one of the question options.'


def validate_question_options(options, answer):
    """Require four distinct, non-empty text options including the answer.

    The frontend compares the chosen option with ``answer`` as plain text,
    so duplicate options or a missing answer would break the evaluation.
    """
    if not has_valid_options(options):
        raise ValidationError({'question_options': OPTIONS_ERROR})
    if answer not in options:
        raise ValidationError({'answer': ANSWER_ERROR})


def has_valid_options(options):
    """True for a list of four distinct, non-empty strings."""
    if not isinstance(options, list) or len(options) != OPTION_COUNT:
        return False
    texts = {
        option for option in options
        if isinstance(option, str) and option.strip()
    }
    return len(texts) == OPTION_COUNT
