"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from accounts.views import home  # Import home view
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from accounts import views
from accounts.views import signup, home, login_view, search_users

urlpatterns = [
    path("home/", home, name="home"),
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    path('search/', search_users, name='search_users'),  # Search URL
]

# Serve static files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # built-in auth routes
    path('accounts/', include('accounts.urls')),  # your app's routes
    path('', home, name='home'),  # Redirect users after login
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])