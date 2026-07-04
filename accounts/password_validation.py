from __future__ import annotations

from string import punctuation

from django.core.exceptions import ValidationError


class TwoCharacterClassValidator:
    def validate(self, password: str, user: object | None = None) -> None:
        character_classes = [
            any(character.isalpha() for character in password),
            any(character.isdigit() for character in password),
            any(character in punctuation for character in password),
            any(
                not character.isalpha()
                and not character.isdigit()
                and character not in punctuation
                for character in password
            ),
        ]

        if sum(character_classes) < 2:
            raise ValidationError(
                "This password must contain at least two character classes.",
                code="password_too_few_character_classes",
            )

    def get_help_text(self) -> str:
        return "Your password must contain at least two character classes."
