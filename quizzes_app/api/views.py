import logging

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Quiz
from ..services.exceptions import QuizGenerationError, VideoTooLongError
from ..services.quiz_pipeline import create_quiz_from_url
from .exceptions import QuizGenerationFailed
from .permissions import IsQuizOwner
from .serializers import (
    QuizCreatedSerializer,
    QuizCreateSerializer,
    QuizSerializer,
)

logger = logging.getLogger(__name__)


class QuizListCreateView(generics.ListCreateAPIView):
    """List own quizzes or generate a new quiz from a YouTube URL.

    POST runs the whole AI pipeline synchronously and answers 201 with the
    complete quiz, as required by the API contract.
    """

    serializer_class = QuizSerializer

    def get_queryset(self):
        own_quizzes = Quiz.objects.filter(owner=self.request.user)
        return own_quizzes.prefetch_related('questions')

    def create(self, request, *args, **kwargs):
        input_serializer = QuizCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        quiz = self.generate_quiz(input_serializer.validated_data['url'])
        output = QuizCreatedSerializer(quiz)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def generate_quiz(self, video_url):
        """Run the pipeline and translate service errors into 400 / 500."""
        try:
            return create_quiz_from_url(self.request.user, video_url)
        except VideoTooLongError as error:
            raise ValidationError({'url': [str(error)]}) from error
        except QuizGenerationError as error:
            logger.exception('Quiz generation failed for %s', video_url)
            raise QuizGenerationFailed() from error


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, patch or delete a single quiz of the authenticated user.

    The queryset deliberately contains all quizzes: an unknown id returns
    404, while another user's quiz is found and then rejected by
    IsQuizOwner with 403, as documented in the API contract.
    """

    queryset = Quiz.objects.prefetch_related('questions')
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
