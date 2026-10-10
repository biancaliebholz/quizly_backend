from rest_framework import serializers

from ..models import Question, Quiz
from ..utils import clean_text


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
