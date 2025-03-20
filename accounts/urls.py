from django.urls import path
from . import views
from accounts.views import signup
from accounts.views import home, search_users
from .views import home, login_view, signup,search_page , search_communities, search_events, view_profile, view_community, join_community, view_event,event_details, profile_settings, edit_profile, join_community, join_community_action, my_communites, leave_community, remove_member, promote_member, create_post
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("home/", home, name="home"),  
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    path("search/", search_page, name="search_page"),
    path('search/users/', search_users, name='search_users'),
    path('search/communities/', search_communities, name='search_communities'),
    path('search/events/', search_events, name='search_events'),
    
    path('profile/<int:user_id>/', view_profile, name='view_profile'),  # View user profile
    path('community/<int:community_id>/', view_community, name='view_community'),  # View community page
    path('community/<int:community_id>/join/', join_community, name='join_community'),  # Join community
    path('event/<int:event_id>/', view_event, name='view_event'),  # View event details
    path('events/<int:event_id>/', event_details, name='event_details'),
    
    path('profile/', profile_settings, name='profile_settings'),
    path('profile/edit/', edit_profile, name='edit_profile'),

    path('joinCommunity/', join_community, name='join_community'),
    path('joinCommunity/<int:community_id>/join/', join_community_action, name='join_community_action'),

    path('myCommunities/', my_communites, name='my_communities'),
    path('community/<int:community_id>/leave/', leave_community, name='leave_community'),

    path('community/<int:community_id>/remove/<int:user_id>/', remove_member, name='remove_member'),

    path('community/<int:community_id>/promote/<int:user_id>/', promote_member, name='promote_member'),

    path('create_post/', create_post, name='create_post'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

