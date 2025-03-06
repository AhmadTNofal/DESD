from django.urls import path
from . import views
from accounts.views import signup

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('', views.home, name='home'),
]
