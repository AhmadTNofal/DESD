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
from accounts.views import signup, home, login_view, search_users, search_communities, search_events, communities, create_community, events, create_event,change_event, cancel_event, join_community, my_communites

urlpatterns = [
    path("home/", home, name="home"),
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    path('search/users/', search_users, name='search_users'),
    path('search/communities/', search_communities, name='search_communities'),
    path('search/events/', search_events, name='search_events'),
    path("communities/", communities, name="communities"),
    path("CreateCommunities/", create_community, name="create_communities"),
    path("events/", events, name="events"),
    path("CreateEvents/", create_event, name="create_events"),
    path("ChangeEvents/", change_event, name="change_event"),
    path("CancelEvents/", cancel_event, name="cancel_event"),
    path("JoinCommunity/", join_community, name="join_community"),
    path("MyCommunities/", my_communites, name="my_communities"),
]

# Serve static files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # built-in auth routes
    path('accounts/', include('accounts.urls')),  # your app's routes
    path('', home, name='home'),  # Redirect users after login
    path("communities/", communities, name="communities"),
    path("CreateCommunities/", create_community, name="create_communities"),
    path("events/", events, name="events"),
    path("CreateEvents/", create_event, name="create_events"),
    path("ChangeEvents/", change_event, name="change_events"),
    path("CancelEvents/", cancel_event, name="cancel_events"),
    path("JoinCommunity/", join_community, name="join_community"),
    path("MyCommunities/", my_communites, name="my_communities"),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])