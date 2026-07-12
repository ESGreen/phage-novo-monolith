from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse

from .question_types import (
    CHOICE_QUESTION_TYPES,
    QUESTION_TYPE_CHOICES,
    RENDER_HINT_CHOICES,
    is_choice_question_type,
    is_valid_render_hint,
)


class Survey(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    description_markdown = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    redirect_after_submission_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "slug"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("surveys:survey-detail", kwargs={"slug": self.slug})

    def clean(self) -> None:
        if self.redirect_after_submission_url and not _is_internal_path(
            self.redirect_after_submission_url,
        ):
            raise ValidationError(
                {"redirect_after_submission_url": "Enter an internal path starting with /."},
            )


def _is_internal_path(value: str) -> bool:
    return value.startswith("/") and not value.startswith("//")


class SurveyQuestion(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    name = models.CharField(max_length=250)
    description_markdown = models.TextField(blank=True)
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES)
    render_hint = models.CharField(max_length=30, choices=RENDER_HINT_CHOICES)
    is_required = models.BooleanField(default=False)
    allows_other = models.BooleanField(default=False)
    other_label = models.CharField(max_length=120, default="Other", blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "id"]
        indexes = [models.Index(fields=["survey", "display_order"])]

    def __str__(self) -> str:
        return self.name

    @property
    def is_choice_based(self) -> bool:
        return is_choice_question_type(self.question_type)

    def clean(self) -> None:
        if self.question_type and self.render_hint and not is_valid_render_hint(
            self.question_type,
            self.render_hint,
        ):
            raise ValidationError(
                {"render_hint": "Render hint is not valid for this question type."},
            )
        if self.allows_other and self.question_type not in CHOICE_QUESTION_TYPES:
            raise ValidationError(
                {"allows_other": "Only choice questions can allow other answers."},
            )


class SurveyChoice(models.Model):
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField(max_length=200)
    value = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "id"]
        indexes = [models.Index(fields=["question", "display_order"])]

    def __str__(self) -> str:
        return self.label

    @property
    def answer_value(self) -> str:
        return self.value or self.label

    def clean(self) -> None:
        if self.question_id and not self.question.is_choice_based:
            raise ValidationError("Choices can only be attached to choice questions.")

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.conditions.exists():
            raise ValidationError("Choice is used by a condition and cannot be deleted.")
        return super().delete(*args, **kwargs)


class SurveyQuestionCondition(models.Model):
    question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    depends_on_question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.CASCADE,
        related_name="dependent_conditions",
    )
    visible_if_choice = models.ForeignKey(
        SurveyChoice,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "depends_on_question", "visible_if_choice"],
                name="unique_survey_question_condition_choice",
            ),
            models.CheckConstraint(
                condition=~Q(question_id=models.F("depends_on_question_id")),
                name="survey_question_condition_not_self",
            ),
        ]

    def clean(self) -> None:
        if self.question_id and self.depends_on_question_id:
            if self.question.survey_id != self.depends_on_question.survey_id:
                raise ValidationError("Condition questions must be in the same survey.")
            if not self.depends_on_question.is_choice_based:
                raise ValidationError("Conditions can only depend on choice questions.")
        if self.visible_if_choice_id and self.depends_on_question_id:
            if self.visible_if_choice.question_id != self.depends_on_question_id:
                raise ValidationError("Condition choice must belong to the controlling question.")


class SurveyResponse(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["survey", "user"], name="unique_survey_response_user")
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.survey}"


class SurveyAnswer(models.Model):
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="answers",
    )
    question_id_snapshot = models.PositiveBigIntegerField()
    question_name_snapshot = models.CharField(max_length=250)
    question_type_snapshot = models.CharField(max_length=30)
    render_hint_snapshot = models.CharField(max_length=30)
    value = models.TextField(default="[]")
    choice_snapshot = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question_id_snapshot", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["response", "question"],
                condition=Q(question__isnull=False),
                name="unique_current_survey_answer_question",
            )
        ]

    def __str__(self) -> str:
        return self.question_name_snapshot
