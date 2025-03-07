from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from accounts.models import CustomUser  

class CustomUserBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """ Authenticate user using the CustomUser model from ORM """
        try:
            user = CustomUser.objects.get(username=username)  
            if check_password(password, user.password):  
                return user  
        except CustomUser.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        """ Retrieve the user from the database using Django ORM """
        try:
            return CustomUser.objects.get(pk=user_id) 
        except CustomUser.DoesNotExist:
            return None
