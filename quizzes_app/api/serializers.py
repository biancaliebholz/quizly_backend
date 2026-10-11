from rest_framework import serializers

from ..models import Question, Quiz
from ..utils import clean_text, normalize_youtube_url

INVALID_URL_MESSAGE = 'Please provide a valid YouTube video URL.'


class QuestionSerializer(serializers.ModelSerializer):
    """Question as documented for list, detail and PATCH (no timestamps)."""

    class Meta:
        model = Question
        fields = ['id', 'question_title', 'question_options', 'answer']
        read_only_fields = fields


class QuizSerializer(serializers.ModelSerializer):
    """Quiz with nested questions; only title and description are writable."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'created_at', 'updated_at',
            'video_url', 'questions',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'video_url']

    def validate_title(self, value):
        """Strip HTML: the frontend renders quiz titles via innerHTML."""
        title = clean_text(value)
        if not title:
            raise serializers.ValidationError('This field may not be blank.')
        return title


class QuestionWithTimestampsSerializer(QuestionSerializer):
    """Question as documented for the POST response (with timestamps)."""

    class Meta(QuestionSerializer.Meta):
        fields = QuestionSerializer.Meta.fields + ['created_at', 'updated_at']
        read_only_fields = fields


class QuizCreatedSerializer(QuizSerializer):
    """Response of POST /api/quizzes/: questions include timestamps."""

    questions = QuestionWithTimestampsSerializer(many=True, read_only=True)


class QuizCreateSerializer(serializers.Serializer):
    """Input of POST /api/quizzes/; the URL is normalized to watch?v=."""

    url = serializers.CharField(max_length=2048)

    def validate_url(self, value):
        video_url = normalize_youtube_url(value)
        if video_url is None:
            raise serializers.ValidationError(INVALID_URL_MESSAGE)
        return video_url
