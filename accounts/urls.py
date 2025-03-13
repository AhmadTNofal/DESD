from django.urls import path
from . import views
from accounts.views import signup
from accounts.views import home, search_users
from .views import home, login_view, signup, profile_settings, edit_profile

urlpatterns = [
    path("home/", home, name="home"),  
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    path('search/', search_users, name='search_users'),  # Search URL
    path('profile/', profile_settings, name='profile_settings'),
    path('profile/edit/', edit_profile, name='edit_profile'),
]

