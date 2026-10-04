from django.core.exceptions import ValidationError


class LetterAndDigitPasswordValidator:
    """HU-AUTH-01: the password must contain letters and numbers.

    The minimum length (8) is enforced by Django's MinimumLengthValidator,
    which is already in AUTH_PASSWORD_VALIDATORS.
    """

    def validate(self, password, user=None):
        errors = []
        if not any(char.isalpha() for char in password):
            errors.append(ValidationError(
                'La contraseña debe contener al menos una letra.',
                code='password_no_letter',
            ))
        if not any(char.isdecimal() for char in password):
            errors.append(ValidationError(
                'La contraseña debe contener al menos un número.',
                code='password_no_digit',
            ))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return 'Tu contraseña debe contener letras y números.'
