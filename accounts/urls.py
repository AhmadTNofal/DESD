from django.urls import path
from . import views
from accounts.views import signup
from accounts.views import home
from .views import home, login_view, signup

urlpatterns = [
    path("home/", home, name="home"),  
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
]

