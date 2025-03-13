from django.urls import path
from . import views
from accounts.views import signup
from accounts.views import home, search_users
from .views import home, login_view, signup, search_communities, search_events, view_profile, view_community, join_community, view_event, profile_settings, edit_profile

urlpatterns = [
    path("home/", home, name="home"),  
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    
    path('search/users/', search_users, name='search_users'),
    path('search/communities/', search_communities, name='search_communities'),
    path('search/events/', search_events, name='search_events'),
    
    path('profile/<int:user_id>/', view_profile, name='view_profile'),  # View user profile
    path('community/<int:community_id>/', view_community, name='view_community'),  # View community page
    path('community/<int:community_id>/join/', join_community, name='join_community'),  # Join community
    path('event/<int:event_id>/', view_event, name='view_event'),  # View event details
    
    path('profile/', profile_settings, name='profile_settings'),
    path('profile/edit/', edit_profile, name='edit_profile'),
]

