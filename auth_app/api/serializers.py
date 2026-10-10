from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    """Validate registration data and create a new user account."""

    confirmed_password = serializers.CharField(
        write_only=True, trim_whitespace=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirmed_password']
        extra_kwargs = {
            'password': {'write_only': True, 'trim_whitespace': False},
            'email': {'validators': []},
        }

    def validate_email(self, value):
        """Reject an email address that is already registered (any case)."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'A user with that email already exists.'
            )
        return value

    def validate(self, attrs):
        """Ensure both passwords match and meet the password policy."""
        if attrs['password'] != attrs['confirmed_password']:
            raise serializers.ValidationError(
                {'confirmed_password': 'Passwords do not match.'}
            )
        self.validate_password_strength(attrs)
        return attrs

    def validate_password_strength(self, attrs):
        """Run Django's password validators against the future user."""
        candidate = User(username=attrs['username'], email=attrs['email'])
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})

    def create(self, validated_data):
        """Create the user with a hashed password."""
        validated_data.pop('confirmed_password')
        return User.objects.create_user(**validated_data)
