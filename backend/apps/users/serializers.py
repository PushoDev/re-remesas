from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Profile, User

EMAIL_TAKEN = 'Ya existe una cuenta con este correo electrónico.'


class ProfileSerializer(serializers.ModelSerializer):
    membership_status = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = ('is_membership_active', 'membership_expires_at', 'membership_status')
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user with its membership profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'is_staff', 'profile')
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            # The model's unique validator is replaced by validate_email so the
            # check is case-insensitive and the message is ours.
            'email': {'validators': []},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(EMAIL_TAKEN, code='email_taken')
        return value

    def validate(self, attrs):
        # Validate with an unsaved user so "password too similar to the
        # email/name" is also checked.
        candidate = User(
            email=attrs.get('email', ''),
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
        )
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    def create(self, validated_data):
        email = validated_data['email']
        try:
            with transaction.atomic():
                # The Profile is created by the post_save signal.
                return User.objects.create_user(
                    username=email,
                    email=email,
                    password=validated_data['password'],
                    first_name=validated_data.get('first_name', ''),
                    last_name=validated_data.get('last_name', ''),
                )
        except IntegrityError:
            # Two simultaneous registrations with the same email.
            raise serializers.ValidationError({'email': [EMAIL_TAKEN]})


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login by email. Emails are stored lowercase, so the input is normalized
    too: "Ana@Example.com " must log in the same account as "ana@example.com"."""

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        if isinstance(email, str):
            attrs[self.username_field] = email.strip().lower()
        return super().validate(attrs)
