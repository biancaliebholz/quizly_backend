from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ..models import Quiz
from .permissions import IsQuizOwner
from .serializers import QuizSerializer


class QuizListView(generics.ListAPIView):
    """List the authenticated user's quizzes (newest first) with questions."""

    serializer_class = QuizSerializer

    def get_queryset(self):
        own_quizzes = Quiz.objects.filter(owner=self.request.user)
        return own_quizzes.prefetch_related('questions')


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
