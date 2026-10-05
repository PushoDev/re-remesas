from django.conf import settings
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth_cookies import delete_refresh_cookie, set_refresh_cookie
from .serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — creates the account and signs the user in.

    The access token goes in the body; the refresh token in an httpOnly cookie.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    # Public endpoint: a stale/invalid Authorization header must not cause a 401.
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response(
            {'user': UserSerializer(user).data, 'access': str(refresh.access_token)},
            status=status.HTTP_201_CREATED,
        )
        set_refresh_cookie(response, refresh)
        return response


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — {email, password} -> {access} + refresh cookie."""

    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            set_refresh_cookie(response, response.data.pop('refresh'))
        return response


class RefreshView(APIView):
    """POST /api/auth/refresh/ — reads the refresh cookie, returns a new access
    token and rotates the cookie. The body is ignored on purpose."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response(
                {'detail': 'No hay una sesión activa.'}, status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = TokenRefreshSerializer(data={'refresh': raw})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, AuthenticationFailed):
            # Invalid, expired, blacklisted, or the user was deactivated.
            response = Response(
                {'detail': 'La sesión expiró. Inicia sesión de nuevo.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            delete_refresh_cookie(response)
            return response

        data = dict(serializer.validated_data)
        new_refresh = data.pop('refresh', raw)
        response = Response(data, status=status.HTTP_200_OK)
        set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklists the refresh token and clears the cookie.

    Idempotent: it always answers 204, with or without a valid session.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass  # already expired/blacklisted: nothing left to invalidate
        response = Response(status=status.HTTP_204_NO_CONTENT)
        delete_refresh_cookie(response)
        return response


class MeView(generics.RetrieveAPIView):
    """GET /api/users/me/ — the authenticated user with its membership state."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
