from django.contrib import admin

from .models import Question, Quiz


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = ('question_title', 'question_options', 'answer')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_title', 'quiz', 'created_at')
    search_fields = ('question_title', 'quiz__title')
    list_select_related = ('quiz',)
    readonly_fields = ('created_at', 'updated_at')
