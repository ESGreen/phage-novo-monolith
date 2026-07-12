from __future__ import annotations

QUESTION_TYPE_TEXT = "text"
QUESTION_TYPE_SINGLE_CHOICE = "single_choice"
QUESTION_TYPE_MULTI_CHOICE = "multi_choice"

QUESTION_TYPE_CHOICES = [
    (QUESTION_TYPE_TEXT, "Text"),
    (QUESTION_TYPE_SINGLE_CHOICE, "Single choice"),
    (QUESTION_TYPE_MULTI_CHOICE, "Multiple choice"),
]

RENDER_HINT_SHORT_TEXT = "short_text"
RENDER_HINT_LONG_TEXT = "long_text"
RENDER_HINT_EMAIL = "email"
RENDER_HINT_PHONE = "phone"
RENDER_HINT_NUMBER = "number"
RENDER_HINT_DATE = "date"
RENDER_HINT_RADIO = "radio"
RENDER_HINT_SELECT = "select"
RENDER_HINT_SCALE = "scale"
RENDER_HINT_CHECKBOXES = "checkboxes"

RENDER_HINT_CHOICES = [
    (RENDER_HINT_SHORT_TEXT, "Short text"),
    (RENDER_HINT_LONG_TEXT, "Long text"),
    (RENDER_HINT_EMAIL, "Email"),
    (RENDER_HINT_PHONE, "Phone"),
    (RENDER_HINT_NUMBER, "Number"),
    (RENDER_HINT_DATE, "Date"),
    (RENDER_HINT_RADIO, "Radio buttons"),
    (RENDER_HINT_SELECT, "Select dropdown"),
    (RENDER_HINT_SCALE, "Scale"),
    (RENDER_HINT_CHECKBOXES, "Checkboxes"),
]

ALLOWED_RENDER_HINTS = {
    QUESTION_TYPE_TEXT: [
        RENDER_HINT_SHORT_TEXT,
        RENDER_HINT_LONG_TEXT,
        RENDER_HINT_EMAIL,
        RENDER_HINT_PHONE,
        RENDER_HINT_NUMBER,
        RENDER_HINT_DATE,
    ],
    QUESTION_TYPE_SINGLE_CHOICE: [
        RENDER_HINT_RADIO,
        RENDER_HINT_SELECT,
        RENDER_HINT_SCALE,
    ],
    QUESTION_TYPE_MULTI_CHOICE: [RENDER_HINT_CHECKBOXES],
}

DEFAULT_RENDER_HINTS = {
    QUESTION_TYPE_TEXT: RENDER_HINT_SHORT_TEXT,
    QUESTION_TYPE_SINGLE_CHOICE: RENDER_HINT_RADIO,
    QUESTION_TYPE_MULTI_CHOICE: RENDER_HINT_CHECKBOXES,
}

CHOICE_QUESTION_TYPES = {QUESTION_TYPE_SINGLE_CHOICE, QUESTION_TYPE_MULTI_CHOICE}


def is_choice_question_type(question_type: str) -> bool:
    return question_type in CHOICE_QUESTION_TYPES


def allowed_render_hint_choices(question_type: str) -> list[tuple[str, str]]:
    allowed = set(ALLOWED_RENDER_HINTS.get(question_type, []))
    return [(value, label) for value, label in RENDER_HINT_CHOICES if value in allowed]


def default_render_hint(question_type: str) -> str:
    return DEFAULT_RENDER_HINTS[question_type]


def is_valid_render_hint(question_type: str, render_hint: str) -> bool:
    return render_hint in ALLOWED_RENDER_HINTS.get(question_type, [])
