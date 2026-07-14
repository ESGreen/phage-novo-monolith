from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Survey, SurveyChoice, SurveyQuestion
from .question_types import allowed_render_hint_choices, default_render_hint
from .services import replace_conditions, validate_condition_update


class SurveyAdminForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = [
            "name",
            "slug",
            "description_markdown",
            "is_active",
            "redirect_after_submission_url",
        ]
        widgets = {"description_markdown": forms.Textarea(attrs={"rows": 8})}

    def clean_slug(self) -> str:
        return self.cleaned_data["slug"].lower()

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if "redirect_after_submission_url" in self.fields:
            self.fields["redirect_after_submission_url"].label = "Redirect after submission"


class SurveyCreateForm(SurveyAdminForm):
    class Meta(SurveyAdminForm.Meta):
        fields = ["name", "slug", "description_markdown"]


class SurveyQuestionAdminForm(forms.ModelForm):
    class Meta:
        model = SurveyQuestion
        fields = ["name", "description_markdown", "render_hint", "is_required"]
        widgets = {"description_markdown": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["render_hint"].choices = allowed_render_hint_choices(
            self.instance.question_type,
        )


class SurveyChoiceForm(forms.ModelForm):
    class Meta:
        model = SurveyChoice
        fields = ["label", "value"]


class SurveyChoiceCreateForm(SurveyChoiceForm):
    def __init__(self, *args: object, question: SurveyQuestion, **kwargs: object) -> None:
        self.question = question
        super().__init__(*args, **kwargs)

    def save(self, commit: bool = True) -> SurveyChoice:
        choice = super().save(commit=False)
        choice.question = self.question
        if commit:
            choice.save()
        return choice


class SurveyQuestionCreateForm(forms.Form):
    name = forms.CharField(max_length=250)
    question_type = forms.ChoiceField(
        choices=SurveyQuestion._meta.get_field("question_type").choices,
    )

    def __init__(self, *args: object, survey, **kwargs: object) -> None:
        self.survey = survey
        super().__init__(*args, **kwargs)

    def save(self, display_order: int) -> SurveyQuestion:
        question_type = self.cleaned_data["question_type"]
        return SurveyQuestion.objects.create(
            survey=self.survey,
            name=self.cleaned_data["name"],
            question_type=question_type,
            render_hint=default_render_hint(question_type),
            display_order=display_order,
        )


class SurveyQuestionOptionsForm(forms.Form):
    allows_other = forms.BooleanField(required=False)
    other_label = forms.CharField(max_length=120, required=False)

    def __init__(self, *args: object, question: SurveyQuestion, **kwargs: object) -> None:
        self.question = question
        initial = {
            "allows_other": question.allows_other,
            "other_label": question.other_label,
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if cleaned_data.get("allows_other") and not cleaned_data.get("other_label"):
            self.add_error("other_label", "Other label is required when other is allowed.")
        return cleaned_data

    def save(self) -> SurveyQuestion:
        self.question.allows_other = self.cleaned_data["allows_other"]
        self.question.other_label = self.cleaned_data["other_label"] or "Other"
        self.question.save(update_fields=["allows_other", "other_label", "updated_at"])
        return self.question


class SurveyConditionForm(forms.Form):
    has_conditions = forms.BooleanField(
        label="Display only under specified conditions",
        required=False,
    )
    depends_on_question = forms.ModelChoiceField(
        label="Controlling question",
        queryset=SurveyQuestion.objects.none(),
        required=False,
    )
    visible_if_choices = forms.ModelMultipleChoiceField(
        label="Visible for choices",
        queryset=SurveyChoice.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args: object, question: SurveyQuestion, **kwargs: object) -> None:
        self.question = question
        self.current_conditions = list(
            question.conditions.select_related("depends_on_question", "visible_if_choice")
        )
        initial = kwargs.pop("initial", {}).copy()
        if self.current_conditions:
            initial.setdefault("has_conditions", True)
            initial.setdefault(
                "depends_on_question",
                self.current_conditions[0].depends_on_question,
            )
            initial.setdefault(
                "visible_if_choices",
                [condition.visible_if_choice for condition in self.current_conditions],
            )
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["depends_on_question"].widget.attrs["data-condition-parent"] = ""
        self.fields["depends_on_question"].queryset = self._eligible_questions()
        selected_parent = self._selected_parent()
        if selected_parent is not None:
            self.fields["visible_if_choices"].queryset = selected_parent.choices.all()

    @property
    def has_late_current_parent(self) -> bool:
        if not self.current_conditions:
            return False
        parent = self.current_conditions[0].depends_on_question
        return parent.display_order >= self.question.display_order

    def _eligible_questions(self):
        queryset = self.question.survey.questions.filter(
            question_type__in=["single_choice", "multi_choice"],
        ).exclude(pk=self.question.pk)
        earlier = queryset.filter(display_order__lt=self.question.display_order)
        if self.current_conditions:
            current_parent = self.current_conditions[0].depends_on_question
            return (earlier | queryset.filter(pk=current_parent.pk)).distinct().order_by(
                "display_order",
                "id",
            )
        return earlier.order_by("display_order", "id")

    def _selected_parent(self) -> SurveyQuestion | None:
        if self.is_bound:
            value = self.data.get(self.add_prefix("depends_on_question"))
            if value:
                try:
                    return SurveyQuestion.objects.get(pk=value)
                except (SurveyQuestion.DoesNotExist, ValueError):
                    return None
        initial_parent = self.initial.get("depends_on_question")
        if isinstance(initial_parent, SurveyQuestion):
            return initial_parent
        if initial_parent:
            try:
                return SurveyQuestion.objects.get(pk=initial_parent)
            except (SurveyQuestion.DoesNotExist, ValueError):
                return None
        return None

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if not cleaned_data.get("has_conditions"):
            return cleaned_data
        parent = cleaned_data.get("depends_on_question")
        choices = list(cleaned_data.get("visible_if_choices") or [])
        if parent is None:
            self.add_error("depends_on_question", "Choose a controlling question.")
        if not choices:
            self.add_error("visible_if_choices", "Choose at least one choice.")
        if parent is not None and choices:
            try:
                validate_condition_update(self.question, parent, choices)
            except ValidationError as error:
                raise forms.ValidationError(error.messages) from error
        return cleaned_data

    def save(self) -> None:
        if not self.cleaned_data.get("has_conditions"):
            replace_conditions(self.question, None, [])
            return
        replace_conditions(
            self.question,
            self.cleaned_data["depends_on_question"],
            list(self.cleaned_data["visible_if_choices"]),
        )
