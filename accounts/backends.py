from django.contrib.auth.backends import BaseBackend
from .models import CustomUser

class CustomUserBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(username=username)
            # WARNING: In production, never compare plaintext passwords.
            if user.password == password:
                return user
        except CustomUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
