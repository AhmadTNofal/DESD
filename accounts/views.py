from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db import connection
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from .models import CustomUser, Community, CommunityMembership, Profile, Notifications, NotificationPreferences
from .forms import CommunityForm, EventForm
from django.urls import reverse
from datetime import date
from .models import Post, Comment 
from .forms import PostForm, CommentForm 
from django.core.files.storage import default_storage 
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from .chat_utils import create_chat_channel, create_user_on_stream
from .chat_utils import get_stream_client
from django.conf import settings
from stream_chat import StreamChat
import cloudinary.uploader
from django.http import JsonResponse
from .models import Like
from .models import Follow
from django.views.decorators.http import require_POST
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.mail import send_mail
from datetime import datetime, timedelta
from uuid import uuid4  # for generating unique Jitsi room names
from django.views.decorators.http import require_GET

def send_notification(user, message, notification_type):
    """Helper function to create and send a notification."""
    # Create notification in the database
    notification = Notifications.objects.create(
        userID=user,
        message=message,
        type=notification_type,
        status="unread"
    )

    # Get user preferences
    try:
        preferences = NotificationPreferences.objects.get(userID=user)
    except NotificationPreferences.DoesNotExist:
        # Create default preferences if none exist
        preferences = NotificationPreferences.objects.create(userID=user)

    # Send email notification if enabled
    email_preference = getattr(preferences, f'email_{notification_type}', False)
    if email_preference:
        send_mail(
            subject=f'New {notification_type.capitalize()} Notification',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    # Send in-app notification via WebSocket if enabled
    in_app_preference = getattr(preferences, f'in_app_{notification_type}', False)
    if in_app_preference:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.userID}',
            {
                'type': 'send_notification',
                'message': message,
                'notification_type': notification_type,
            }
        )
@login_required
def home(request):
    posts = Post.objects.all().order_by('-createdAt')

    # Precompute if the post is liked by the current user
    for post in posts:
        post.is_liked_by_user = post.likes.filter(user=request.user).exists()

    unread_count = 0
    try:
        client = get_stream_client()
        user_id = str(request.user.userID)

        channels_response = client.query_channels(
            {"members": {"$in": [user_id]}},
            {"last_message_at": -1}
        )
        channels = channels_response.get("channels", [])

        for ch in channels:
            for read in ch.get("read", []):
                if read["user"]["id"] == user_id:
                    unread_count += read.get("unread_messages", 0)
    except Exception as e:
        print("🔴 Stream error in home view:", e)

    # Add count of unread notifications
    unread_notifications = Notifications.objects.filter(userID=request.user, status='unread').count()

    return render(request, "profile/home.html", {
        "posts": posts,
        "unread_count": unread_count,
        "unread_notifications": unread_notifications,  # Add this
        "permission": request.user.Permission
    })

def search_page(request):
    return render(request, "profile/search.html")

def search_users(request):
    """ Allow users to search for others by username, email, surname, or interests """
    query = request.GET.get('q', '').strip()  # Get the search query

    if not query:
        return render(request, 'profile/search_results.html', {'results': None, 'query': query})

    user_id = request.user.userID if request.user.is_authenticated else None
    if user_id:
        # Exclude current user if authenticated
        query_sql = """
            SELECT u.userID, u.username, u.surname, u.email, 
                   p.profile_picture 
            FROM User u
            LEFT JOIN Profiles p ON u.userID = p.userID
            WHERE (
                u.username LIKE %s OR 
                u.email LIKE %s OR 
                u.surname LIKE %s OR 
                p.interests LIKE %s
            )
            AND u.userID != %s
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", user_id]
    else:
        query_sql = """
            SELECT u.userID, u.username, u.surname, u.email, 
                   p.profile_picture 
            FROM User u
            LEFT JOIN Profiles p ON u.userID = p.userID
            WHERE (
                u.username LIKE %s OR 
                u.email LIKE %s OR 
                u.surname LIKE %s OR 
                p.interests LIKE %s
            )
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"]

    results = CustomUser.objects.raw(query_sql, params)
    return render(request, 'profile/search_results.html', {'results': results, 'query': query})


def search_communities(request):
    """ Allow users to search for communities by name or category """
    
    query = request.GET.get('q', '').strip()  # Get search query

    # Exclude communities created by the logged-in user
    user_id = request.user.userID if request.user.is_authenticated else None
    results = Community.objects.filter(
        (Q(name__icontains=query) | Q(communityCategory__icontains=query)) &
        ~Q(createdBy_id=user_id)  # Exclude communities created by the user
    ) if query else None  # Return results only if query is not empty

    return render(request, 'Communities/search_communities.html', {'results': results, 'query': query})

def search_events(request):
    """ Allow users to search for events by title, location, or community name """
    
    query = request.GET.get('q', '').strip()  # Get search query

    results = []
    if query:
        user_id = request.user.userID if request.user.is_authenticated else None
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, c.name as communityName
                FROM Events e
                JOIN Communities c ON e.communityID = c.communityID
                WHERE (e.eventTitle LIKE %s OR e.location LIKE %s OR c.name LIKE %s)
                AND e.createdBy != %s
            """, [f"%{query}%", f"%{query}%", f"%{query}%", user_id])
            
            results = cursor.fetchall()  # Fetch raw query results

    return render(request, 'Events/search_events.html', {'results': results, 'query': query})

@require_GET
def search_suggestions(request):
    query = request.GET.get("q", "").strip()
    search_type = request.GET.get("type", "users").lower()
    suggestions = []

    if not query:
        return JsonResponse({"suggestions": []})

    with connection.cursor() as cursor:
        if search_type == "users":
            cursor.execute("""
                SELECT u.userID, u.username, p.interests, p.profile_picture
                FROM User u
                LEFT JOIN Profiles p ON u.userID = p.userID
                WHERE u.username LIKE %s OR u.email LIKE %s OR p.interests LIKE %s
                LIMIT 10
            """, [f"%{query}%", f"%{query}%", f"%{query}%"])
            rows = cursor.fetchall()
            suggestions = [
                {
                    "id": row[0],
                    "name": row[1],
                    "interests": row[2] or "",
                    "profile_picture": row[3] or ""
                }
                for row in rows
            ]

        elif search_type == "communities":
            cursor.execute("""
                SELECT c.communityID, c.name, COUNT(cm.userID) as member_count
                FROM Communities c
                LEFT JOIN CommunityMemberships cm ON c.communityID = cm.communityID
                WHERE c.name LIKE %s
                GROUP BY c.communityID, c.name
                ORDER BY member_count DESC
                LIMIT 10
            """, [f"%{query}%"])
            rows = cursor.fetchall()
            suggestions = [
                {
                    "id": row[0],
                    "name": row[1],
                    "members": row[2]
                }
                for row in rows
            ]

        elif search_type == "events":
            cursor.execute("""
                SELECT eventID, eventTitle, eventDate, eventTime
                FROM Events
                WHERE eventTitle LIKE %s
                ORDER BY eventDate, eventTime
                LIMIT 10
            """, [f"%{query}%"])
            rows = cursor.fetchall()
            suggestions = [
                {
                    "id": row[0],
                    "name": row[1],
                    "date": row[2].strftime("%Y-%m-%d"),
                    "time": row[3].strftime("%H:%M")
                }
                for row in rows
            ]

    return JsonResponse({"suggestions": suggestions})

from django.shortcuts import render, get_object_or_404
from .models import CustomUser, Profile, Post, Follow

def view_profile(request, user_id):
    user = CustomUser.objects.get(userID=user_id)
    profile = Profile.objects.filter(user=user).first()
    posts = Post.objects.filter(user=user).exclude(image='').order_by('-createdAt')

    # People who follow this user
    followers = CustomUser.objects.filter(following__following=user)

    # People this user follows
    following = CustomUser.objects.filter(followers__follower=user)

    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=user).exists()

    return render(request, 'profile/view_profile.html', {
        'user': user,
        'profile': profile,
        'posts': posts,
        'followers': followers,
        'following': following,
        'followers_count': followers.count(),
        'following_count': following.count(),
        'is_following': is_following,
    })

@login_required
def user_profile(request, username):
    user = get_object_or_404(CustomUser, username=username)
    profile = Profile.objects.filter(user=user).first()
    posts = Post.objects.filter(userID=user).order_by('-createdAt')

    return render(request, 'accounts/user_profile.html', {
        'profile_user': user,
        'profile': profile,
        'posts': posts,
    })

def view_community(request, community_id):
    """ Display community details and allow users to join. """
    community = Community.objects.get(communityID=community_id)  # Fetch community
    is_member = CommunityMembership.objects.filter(communityID=community, userID=request.user).exists()  # Check if user is a member
    return render(request, 'Communities/view_community.html', {'community': community, 'is_member': is_member})

def join_community(request, community_id):
    """ Allows users to join a community if they are not already members. """
    community = Community.objects.get(communityID=community_id)  # Fetch community

    if not CommunityMembership.objects.filter(communityID=community, userID=request.user).exists():
        CommunityMembership.objects.create(
            communityID=community,
            userID=request.user,
            role="Member"
        )
        messages.success(request, "You have successfully joined the community!")

    return redirect('view_community', community_id=community_id)

def view_event(request, event_id):
    """ Display full details of an event. """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, c.name as communityName
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
            WHERE e.eventID = %s
        """, [event_id])
        event = cursor.fetchone()  # Fetch event details

    if not event:
        messages.error(request, "Event not found.")
        return redirect('search_events')

    event_data = {
        "eventID": event[0],
        "eventTitle": event[1],
        "eventDate": event[2],
        "eventTime": event[3].strftime("%H:%M"),
        "location": event[4],
        "virtualLink": event[5],
        "communityName": event[6]
    }

    return render(request, 'Events/view_event.html', {"event": event_data})

@csrf_exempt
def login_view(request):
    """Custom login view to authenticate users and redirect them to home."""
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        
        user = authenticate(request, username=username, password=password)  

        if user is not None:
            login(request, user)  # Log in the user
            messages.success(request, "Login successful!")
            return redirect("home")  

        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "registration/login.html")  

def signup(request):
    if request.method == "POST":
        username = request.POST["username"]
        surname = request.POST["surname"]
        email = request.POST["email"]
        phoneNumber = request.POST["phoneNumber"]
        password = make_password(request.POST["password"])  # Hashing the password
        bio = request.POST.get("bio", "")
        major = request.POST.get("major", "")
        academicYear = request.POST.get("academicYear", "")
        campusInvolvement = request.POST.get("campusInvolvement", "")
        date_of_birth = request.POST.get("date_of_birth")
        city = request.POST.get("city")
        street_name = request.POST.get("street_name")
        post_code = request.POST.get("post_code")

        try:
            with connection.cursor() as cursor:
                # ✅ Check if the username already exists
                cursor.execute("SELECT COUNT(*) FROM `User` WHERE username = %s", [username])
                username_exists = cursor.fetchone()[0] > 0

                # ✅ Check if the email is already registered
                cursor.execute("SELECT COUNT(*) FROM `User` WHERE email = %s", [email])
                email_exists = cursor.fetchone()[0] > 0

                if username_exists:
                    messages.error(request, "Username is already taken. Please choose another.")
                if email_exists:
                    messages.error(request, "Email is already in use. Please use a different email.")

                if username_exists or email_exists:
                    return redirect("signup")  # Redirect back to signup page to show error

                # ✅ If username & email are unique, proceed with signup
                cursor.execute("""
                    INSERT INTO `User` (username, surname, email, phoneNumber, password, Permission)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [username, surname, email, phoneNumber, password, "user"])

                # Get the userID of the newly inserted user
                cursor.execute("SELECT LAST_INSERT_ID()")
                user_id = cursor.fetchone()[0]  # Fetch userID from the database

                if not user_id:
                    raise ValueError("User ID not retrieved. Profile insertion aborted.")

                # Insert into Profiles table
                cursor.execute("""
                    INSERT INTO `Profiles` (userID, bio, major, academicYear, campusInvolvement, date_of_birth, city, street_name, post_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [user_id, bio, major, academicYear, campusInvolvement, date_of_birth, city, street_name, post_code])

            # Authenticate and Log in the user
            user = CustomUser.objects.get(userID=user_id)  # Get the newly created user
            user.backend = 'django.contrib.auth.backends.ModelBackend'  # Required to log in manually
            login(request, user)  # Log the user in

            # Create default notification preferences for the new user
            NotificationPreferences.objects.create(userID=user)

            messages.success(request, "Signup successful! Redirecting to homepage...")
            return redirect("home")  # Redirect to homepage

        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    return render(request, 'registration/signup.html')

@login_required
def communities(request):
    """ Display all communities and events related to the user. """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Assuming `userID` is the primary key in `CustomUser`

    # Fetch communities the user is a member of
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name, c.communityDescription, c.communityCategory 
            FROM Communities c
            JOIN CommunityMemberships cm ON c.communityID = cm.communityID
            WHERE cm.userID = %s
        """, [user_id])
        
        joined_communities = cursor.fetchall()  # List of (communityID, name, description, category)

    # Fetch communities the user is NOT in
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name, c.communityDescription, c.communityCategory 
            FROM Communities c
            WHERE c.communityID NOT IN (
                SELECT communityID FROM CommunityMemberships WHERE userID = %s
            )
        """, [user_id])
        
        non_joined_communities = cursor.fetchall()  # List of (communityID, name, description, category)

    # Fetch events from the user's communities
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, c.name AS communityName
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
            JOIN CommunityMemberships cm ON cm.communityID = c.communityID
            WHERE cm.userID = %s
            ORDER BY e.eventDate ASC
        """, [user_id])
        
        events = cursor.fetchall()  # List of (eventID, eventTitle, eventDate, eventTime, location, virtualLink, communityName)

    return render(request, 'Communities/community.html', {
        'joined_communities': joined_communities,
        'non_joined_communities': non_joined_communities,
        'events': events
    })

@login_required
def create_community(request):
    if request.method == "POST":
        form = CommunityForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            description = form.cleaned_data["communityDescription"]
            category = form.cleaned_data["communityCategory"]
            now = timezone.now()

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO CommunityRequests (
                        name, communityDescription, communityCategory,
                        requestedBy, requestedAt, status
                    )
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, [name, description, category, request.user.userID, now])

            messages.success(request, "Community request submitted for approval.")
            return redirect("communities")
        else:
            print("Form Errors:", form.errors)
            messages.error(request, "Error submitting community request. Please check the form.")
    else:
        form = CommunityForm()

    return render(request, "Communities/create_community.html", {"form": form})

@login_required
def profile_settings(request):
    user = request.user  # Get logged-in user
    profile = Profile.objects.filter(user=user).first()  # Use `.first()` to avoid errors if profile doesn't exist

    if not profile:
        messages.error(request, "Profile not found.")
        return redirect("home")

    # Debugging Output
    print(f"User: {user.username}, Profile ID: {profile.profileID}, Bio: {profile.bio}, Major: {profile.major}, Year: {profile.academicYear}, Involvement: {profile.campusInvolvement}")

    return render(request, 'profile/profile.html', {'user': user, 'profile': profile})

@login_required
def edit_profile(request):
    user = request.user  
    profile, created = Profile.objects.get_or_create(user=user)  

    if request.method == "POST":
        user.username = request.POST["username"]
        user.email = request.POST["email"]
        user.surname = request.POST.get("surname", "")
        user.phoneNumber = request.POST.get("phoneNumber", "")

        profile.bio = request.POST.get("bio", profile.bio)
        profile.major = request.POST.get("major", profile.major)
        profile.academicYear = request.POST.get("academicYear", profile.academicYear)
        profile.campusInvolvement = request.POST.get("campusInvolvement", profile.campusInvolvement)
        profile.interests = request.POST.get("interests", profile.interests)


        # ✅ Handle Profile Picture Upload
        if 'profile_picture' in request.FILES:
            uploaded_file = request.FILES['profile_picture']
            result = cloudinary.uploader.upload(uploaded_file, folder="profile_pictures/")
            profile.profile_picture = result['secure_url']
        try:
            user.save()  
            profile.save()  
            messages.success(request, "Profile updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")

        return redirect("profile_settings")

    return render(request, "profile/profile.html", {"user": user, "profile": profile})

@login_required
def events(request):
    """ Fetch and filter events based on user input and include available locations """
    query = request.GET.get("q", "").strip()
    selected_date = request.GET.get("date", "")
    selected_time = request.GET.get("time", "")
    online_filter = request.GET.get("online", "")
    location_filter = request.GET.get("location", "")

    user_id = request.user.userID if request.user.is_authenticated else None

    # Fetch events from communities the user is part of
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, e.description, c.name as communityName
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
            JOIN CommunityMemberships cm ON cm.communityID = c.communityID
            WHERE e.eventDate >= %s AND cm.userID = %s
        """, [date.today(), user_id])

        events = cursor.fetchall()

    # Fetch distinct locations for filtering
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT location FROM Events WHERE location IS NOT NULL ORDER BY location")
        locations = [row[0] for row in cursor.fetchall()]

    # Convert raw data into dictionaries
    filtered_events = []
    for event in events:
        event_id, title, event_date, event_time, location, virtual_link, description, community_name = event

        event_data = {
            "eventID": event_id,
            "eventTitle": title,
            "eventDate": event_date,
            "eventTime": event_time.strftime("%H:%M"),
            "location": location,
            "virtualLink": virtual_link,
            "description": description,
            "is_online": virtual_link is not None,
            "communityName": community_name
        }

        # Apply filters
        if query and query.lower() not in title.lower():
            continue
        if selected_date and str(event_date) < selected_date:
            continue
        if selected_time and event_data["eventTime"] < selected_time:
            continue
        if online_filter == "yes" and not event_data["is_online"]:
            continue
        if online_filter == "no" and event_data["is_online"]:
            continue
        if location_filter and location_filter.lower() not in (location or "").lower():
            continue

        filtered_events.append(event_data)

    return render(request, "Events/events.html", {
        "events": filtered_events,
        "locations": locations,
        "query": query
    })

@login_required
def event_details(request, event_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, e.description, c.name as communityName, e.createdBy, e.meetingLaunched
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
            WHERE e.eventID = %s
        """, [event_id])

        event = cursor.fetchone()

    if not event:
        return redirect("events")

    event_data = {
        "eventTitle": event[0],
        "eventDate": event[1],
        "eventTime": event[2].strftime("%H:%M"),
        "location": event[3],
        "virtualLink": event[4],
        "description": event[5],
        "communityName": event[6],
        "createdBy": event[7],
        "meetingLaunched": event[8],
    }

    from datetime import datetime, timedelta
    now = datetime.now()
    event_datetime = datetime.combine(event[1], event[2])
    accessible_now = now >= (event_datetime - timedelta(minutes=5))

    event_data["is_creator"] = (request.user.userID == event[7])
    event_data["accessible_now"] = accessible_now

    return render(request, "Events/event_details.html", {"event": event_data})


@login_required
def create_event(request):
    user_id = request.user.userID

    # Fetch communities where user is Admin
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.communityID, c.name FROM CommunityMemberships cm "
            "JOIN Communities c ON cm.communityID = c.communityID "
            "WHERE cm.userID = %s AND cm.role = 'Admin'", [user_id]
        )
        communities = cursor.fetchall()

    if not communities:
        return render(request, 'Events/create_event.html', {'error': "You don't have permission to create events."})

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            community_id = request.POST.get("communityID")
            is_online = request.POST.get("onlineEvent")
            location = data['location'] if not is_online else None
            description = data['description']
            virtual_link = None

            # ✅ If online, generate Jitsi link
            if is_online:
                room_name = f"Jitsi_{uuid4().hex[:10]}"
                virtual_link = f"https://meet.jit.si/{room_name}"

            # ✅ Insert event into DB
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO Events (communityID, eventTitle, eventDate, eventTime, location, virtualLink, description, createdBy, createdAt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [community_id, data['eventTitle'], data['eventDate'], data['eventTime'], location, virtual_link, description, user_id]
                )

            # ✅ Notify members of the new event
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT userID FROM CommunityMemberships WHERE communityID = %s AND userID != %s",
                    [community_id, user_id]
                )
                members = cursor.fetchall()

            for member in members:
                member_id = member[0]
                member_user = CustomUser.objects.get(userID=member_id)
                send_notification(
                    user=member_user,
                    message=f"New event '{data['eventTitle']}' created in {communities[0][1]}",
                    notification_type="event"
                )

            messages.success(request, "Event created successfully!")
            return redirect('events')
    else:
        form = EventForm()

    return render(request, 'Events/create_event.html', {'form': form, 'communities': communities})

@login_required
def change_event(request):
    user_id = request.user.userID

    with connection.cursor() as cursor:
        cursor.execute("SELECT eventID, eventTitle FROM Events WHERE createdBy = %s", [user_id])
        events = cursor.fetchall()

    selected_event = None

    if request.method == "POST":
        event_id = request.POST.get("eventID")

        if event_id:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT eventID, eventTitle, eventDate, eventTime, location, virtualLink, description "
                    "FROM Events WHERE eventID = %s AND createdBy = %s",
                    [event_id, user_id]
                )
                selected_event = cursor.fetchone()

        if "updateEvent" in request.POST:
            event_title = request.POST.get("eventTitle")
            event_date = request.POST.get("eventDate")
            event_time = request.POST.get("eventTime")
            location = request.POST.get("location") if "onlineEvent" not in request.POST else None
            virtual_link = selected_event[5]  # existing link by default

            # ✅ If switching to online and no existing Jitsi, generate new one
            if "onlineEvent" in request.POST and not virtual_link:
                room_name = f"Jitsi_{uuid4().hex[:10]}"
                virtual_link = f"https://meet.jit.si/{room_name}"
            elif "onlineEvent" not in request.POST:
                virtual_link = None

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT communityID FROM Events WHERE eventID = %s",
                    [event_id]
                )
                community_id = cursor.fetchone()[0]

                cursor.execute(
                    "UPDATE Events SET eventTitle=%s, eventDate=%s, eventTime=%s, location=%s, virtualLink=%s, description=%s "
                    "WHERE eventID=%s",
                    [event_title, event_date, event_time, location, virtual_link, request.POST.get("description"), event_id]
                )

            # ✅ Notify members
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT userID FROM CommunityMemberships WHERE communityID = %s AND userID != %s",
                    [community_id, user_id]
                )
                members = cursor.fetchall()

            for member in members:
                member_id = member[0]
                member_user = CustomUser.objects.get(userID=member_id)
                send_notification(
                    user=member_user,
                    message=f"Event '{event_title}' has been updated",
                    notification_type="event"
                )

            messages.success(request, "Event updated successfully!")
            return redirect('change_events')

    return render(request, 'Events/change_event.html', {'events': events, 'selected_event': selected_event})

@login_required
def cancel_event(request):
    user_id = request.user.userID

    with connection.cursor() as cursor:
        cursor.execute("SELECT eventID, eventTitle FROM Events WHERE createdBy = %s", [user_id])
        events = cursor.fetchall()

    if request.method == "POST":
        event_id = request.POST.get("eventID")

        if event_id:
            with connection.cursor() as cursor:
                cursor.execute("SELECT communityID, eventTitle FROM Events WHERE eventID = %s AND createdBy = %s", [event_id, user_id])
                result = cursor.fetchone()
                community_id, event_title = result

            # ✅ Notify members
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT userID FROM CommunityMemberships WHERE communityID = %s AND userID != %s",
                    [community_id, user_id]
                )
                members = cursor.fetchall()

            for member in members:
                member_id = member[0]
                member_user = CustomUser.objects.get(userID=member_id)
                send_notification(
                    user=member_user,
                    message=f"Event '{event_title}' has been canceled",
                    notification_type="event"
                )

            # ✅ Delete event
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM Events WHERE eventID = %s AND createdBy = %s", [event_id, user_id])

            messages.success(request, "Event canceled successfully!")
            return redirect('cancel_events')

    return render(request, 'Events/cancel_event.html', {'events': events})



@login_required
def embedded_meeting(request, room_slug):
    user_id = request.user.userID

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT eventID, createdBy, virtualLink, meetingLaunched, eventDate, eventTime
            FROM Events
            WHERE virtualLink LIKE %s
        """, [f"https://meet.jit.si/{room_slug}"])
        event = cursor.fetchone()

    if not event:
        messages.error(request, "Event not found.")
        return redirect("home")

    event_id, created_by_id, virtual_link, meeting_launched, event_date, event_time = event

    # Combine date and time into a single datetime object
    event_datetime = datetime.combine(event_date, event_time)
    now = datetime.now()

    # Calculate if we're within 5 minutes before the event
    is_within_five_minutes = now >= (event_datetime - timedelta(minutes=5))

    if (user_id == created_by_id or request.user.Permission == "Admin") and not meeting_launched:
        # ✅ Creator starts the meeting, set the flag
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE Events SET meetingLaunched = TRUE WHERE eventID = %s
            """, [event_id])
        return render(request, 'Events/embedded_meeting.html', {
            'room_name': room_slug
        })

    elif meeting_launched and is_within_five_minutes:
        # ✅ Any user can join if meeting launched AND within 5 minutes
        return render(request, 'Events/embedded_meeting.html', {
            'room_name': room_slug
        })

    elif not is_within_five_minutes:
        # ⏰ Too early for non-creators
        minutes_left = int((event_datetime - now).total_seconds() // 60)
        messages.warning(request, f"The meeting will be available {minutes_left} minutes before it starts.")
        return redirect("events")

    else:
        # 🛑 Creator hasn't launched it yet
        messages.warning(request, "The meeting hasn't started yet. Please wait for the event creator.")
        return redirect("events")




@login_required
def join_community(request):
    """ Display communities that the user has NOT joined with full details. """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Assuming `userID` is the primary key in `CustomUser`

    # Fetch communities that the user has NOT joined, including details
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name, c.communityDescription, c.communityCategory, u.username as createdBy, c.createdAt
            FROM Communities c
            JOIN User u ON c.createdBy = u.userID
            WHERE c.communityID NOT IN (
                SELECT communityID FROM CommunityMemberships WHERE userID = %s
            )
        """, [user_id])
        non_joined_communities = cursor.fetchall()  # List of (communityID, name, description, category, createdBy, createdAt)

    return render(request, 'Communities/join_community.html', {
        'non_joined_communities': non_joined_communities
    })

@login_required
def join_community_action(request, community_id):
    """ Allow users to join a community as a 'Member' """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Ensure this matches your database schema

    # Check if the user is already a member
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM CommunityMemberships WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        is_member = cursor.fetchone()[0] > 0  # If count > 0, user is already a member

    if not is_member:
        # Insert new membership as "Member"
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO CommunityMemberships (communityID, userID, role, joinedAt)
                VALUES (%s, %s, 'Member', NOW())
            """, [community_id, user_id])

        # Notify community admins about the new member
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT userID FROM CommunityMemberships WHERE communityID = %s AND role = 'Admin'",
                [community_id]
            )
            admins = cursor.fetchall()

        community = Community.objects.get(communityID=community_id)
        for admin in admins:
            admin_id = admin[0]
            admin_user = CustomUser.objects.get(userID=admin_id)
            send_notification(
                user=admin_user,
                message=f"{user.username} has joined your community '{community.name}'",
                notification_type="community"
            )

        messages.success(request, "You have successfully joined the community!")

    return redirect('join_community')  

@login_required
def my_communites(request):
    """ Display communities that the user has joined along with their role. """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Assuming `userID` is the primary key in `CustomUser`

    # Fetch communities where the user is a member, including their role and admin list
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name, c.communityDescription, c.communityCategory, 
                    GROUP_CONCAT(DISTINCT u.username SEPARATOR ', ') AS admins, 
                    cm.role, c.createdAt
            FROM Communities c
            JOIN CommunityMemberships cm ON c.communityID = cm.communityID
            JOIN CommunityMemberships admins ON c.communityID = admins.communityID
            JOIN User u ON admins.userID = u.userID
            WHERE cm.userID = %s
            AND admins.role = 'Admin'
            GROUP BY c.communityID, c.name, c.communityDescription, c.communityCategory, cm.role, c.createdAt
        """, [user_id])
        
        joined_communities = cursor.fetchall()  # List of (communityID, name, description, category, admins, role, createdAt)

    return render(request, 'Communities/my_communities.html', {
        'joined_communities': joined_communities
    })

@login_required
def leave_community(request, community_id):
    """ Allows a user to leave a community if they are a member. """

    user = request.user  # Get logged-in user
    user_id = user.userID  # Assuming `userID` is the primary key in `CustomUser`

    # Check if the user is a member of the community
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        is_member = cursor.fetchone()[0] > 0  # If count > 0, user is a member

    if is_member:
        # Remove the user from the community
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM CommunityMemberships 
                WHERE communityID = %s AND userID = %s
            """, [community_id, user_id])

        messages.success(request, "You have successfully left the community.")
    else:
        messages.error(request, "You are not a member of this community.")

    return redirect('communities')  # Redirect back to the main communities page

@login_required
def view_community(request, community_id):
    """ Display community details with different views for Admins and Members. """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Assuming `userID` is the primary key in `CustomUser`

    # Fetch community details
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name, c.communityDescription, c.communityCategory, 
                   GROUP_CONCAT(DISTINCT u.username SEPARATOR ', ') AS admins, 
                   c.createdAt
            FROM Communities c
            JOIN CommunityMemberships admins ON c.communityID = admins.communityID
            JOIN User u ON admins.userID = u.userID
            WHERE c.communityID = %s
            AND admins.role = 'Admin'
            GROUP BY c.communityID, c.name, c.communityDescription, c.communityCategory, c.createdAt
        """, [community_id])

        community = cursor.fetchone()  # Fetch community details
    
    if not community:
        messages.error(request, "Community not found.")
        return redirect("communities")

    # Fetch all members of the community
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.userID, u.username, cm.role
            FROM CommunityMemberships cm
            JOIN User u ON cm.userID = u.userID
            WHERE cm.communityID = %s
        """, [community_id])

        members = cursor.fetchall()  # List of (userID, username, role)

    # Check if the logged-in user is a Member
    is_member = False
    user_role = "Guest"
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT role FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        role = cursor.fetchone()
    
    if role:
        is_member = True  # The user is part of the community
        user_role = role[0]  # Set the user's role (Admin or Member)

    return render(request, "Communities/view_community.html", {
        "community": community,
        "members": members,
        "user_role": user_role,
        "is_member": is_member
    })

@login_required
def remove_member(request, community_id, user_id):
    """ Allows an Admin to remove a Member from a community. """
    
    admin_id = request.user.userID  # Get logged-in admin user ID

    # Check if the logged-in user is an Admin of this community
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s AND role = 'Admin'
        """, [community_id, admin_id])
        is_admin = cursor.fetchone()[0] > 0  # If count > 0, user is an Admin

    if not is_admin:
        messages.error(request, "You do not have permission to remove members.")
        return redirect('view_community', community_id=community_id)

    # Check if the user being removed is an Admin
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT role FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        member_role = cursor.fetchone()

    if member_role and member_role[0] == "Admin":
        messages.error(request, "You cannot remove another Admin.")
        return redirect('view_community', community_id=community_id)

    # Remove the member from the community
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM CommunityMemberships WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])

    messages.success(request, "Member removed successfully.")
    return redirect('view_community', community_id=community_id)

@login_required
def promote_member(request, community_id, user_id):
    """ Allows an Admin to promote a Member to Admin. """
    
    admin_id = request.user.userID  # Get logged-in Admin's ID

    # Check if the logged-in user is an Admin of this community
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s AND role = 'Admin'
        """, [community_id, admin_id])
        is_admin = cursor.fetchone()[0] > 0  # If count > 0, user is an Admin

    if not is_admin:
        messages.error(request, "You do not have permission to promote members.")
        return redirect('view_community', community_id=community_id)

    # Check if the user being promoted is already an Admin
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT role FROM CommunityMemberships 
            WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        member_role = cursor.fetchone()

    if member_role and member_role[0] == "Admin":
        messages.error(request, "This user is already an Admin.")
        return redirect('view_community', community_id=community_id)

    # Promote the member to Admin
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE CommunityMemberships 
            SET role = 'Admin' 
            WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])

    messages.success(request, "Member successfully promoted to Admin.")
    return redirect('view_community', community_id=community_id)

@login_required
def join_community_action(request, community_id):
    """ Allows users to join a community as a 'Member' and stay on the same page. """
    
    user = request.user  # Get logged-in user
    user_id = user.userID  # Ensure this matches your database schema

    # Check if the user is already a member
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM CommunityMemberships WHERE communityID = %s AND userID = %s
        """, [community_id, user_id])
        is_member = cursor.fetchone()[0] > 0  # If count > 0, user is already a member

    if not is_member:
        # Insert new membership as "Member"
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO CommunityMemberships (communityID, userID, role, joinedAt)
                VALUES (%s, %s, 'Member', NOW())
            """, [community_id, user_id])

        # Notify community admins about the new member
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT userID FROM CommunityMemberships WHERE communityID = %s AND role = 'Admin'",
                [community_id]
            )
            admins = cursor.fetchall()

        community = Community.objects.get(communityID=community_id)
        for admin in admins:
            admin_id = admin[0]
            admin_user = CustomUser.objects.get(userID=admin_id)
            send_notification(
                user=admin_user,
                message=f"{user.username} has joined your community '{community.name}'",
                notification_type="community"
            )

        messages.success(request, "You have successfully joined the community!")

    # Redirect back to the same page the user came from
    return redirect(request.META.get('HTTP_REFERER', 'communities'))

@login_required
def create_post(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user

            if 'image' in request.FILES:
                uploaded_image = request.FILES['image']
                result = cloudinary.uploader.upload(uploaded_image, folder="post_images/")
                post.image = result['secure_url']

            post.save()

            # Notify followers about the new post
            followers = CustomUser.objects.filter(following__following=request.user)
            for follower in followers:
                send_notification(
                    user=follower,
                    message=f"{request.user.username} created a new post",
                    notification_type="post"
                )

            messages.success(request, "Post created successfully!")
            return redirect("home")
    else:
        form = PostForm()  # <- here you define `form` for GET

    return render(request, "profile/create_post.html", {"form": form})

@login_required
def admin_view(request):
    if request.user.Permission != "Admin":
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You are not authorized to access this page.")
    
    users = CustomUser.objects.all()
    communities = Community.objects.all()

    # Fetch events
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, c.name AS communityName
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
        """)
        events = cursor.fetchall()

    # Fetch pending community requests
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cr.requestID, cr.name, cr.communityDescription, cr.communityCategory,
                   u.username, cr.requestedAt
            FROM CommunityRequests cr
            JOIN User u ON cr.requestedBy = u.userID
            WHERE cr.status = 'pending'
        """)
        pending_requests = cursor.fetchall()

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.virtualLink, e.meetingLaunched
            FROM Events e
            WHERE e.virtualLink IS NOT NULL
            ORDER BY e.eventDate DESC, e.eventTime DESC
        """)
        virtual_sessions = cursor.fetchall()

    return render(request, "profile/admin.html", {
        "users": users,
        "communities": communities,
        "events": events,
        "pending_requests": pending_requests,
        "virtual_sessions": virtual_sessions,
        "permission": request.user.Permission
    })

@require_POST
@login_required
def promote_user(request):
    """ Promote a user to Admin after verifying password """
    user_id = request.POST.get("user_id")
    password = request.POST.get("password")

    # Verify password
    if not request.user.check_password(password):
        messages.error(request, "Incorrect password. Promotion cancelled.")
        return redirect("admin_view")

    # Update permission
    try:
        target_user = CustomUser.objects.get(userID=user_id)
        target_user.Permission = "Admin"
        target_user.save()
        messages.success(request, f"{target_user.username} has been promoted to Admin.")
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")

    return redirect("admin_view")

@require_POST
@login_required
def remove_community(request):
    """ Remove a community and its related events after verifying the admin's password """
    community_id = request.POST.get("community_id")
    password = request.POST.get("password")

    # Verify the admin's password
    if not request.user.check_password(password):
        messages.error(request, "Incorrect password. Community removal cancelled.")
        return redirect("admin_view")

    # Check if the user is an Admin
    if request.user.Permission != "Admin":
        messages.error(request, "You do not have permission to remove communities.")
        return redirect("admin_view")

    # Remove the community and its related events
    try:
        community = Community.objects.get(communityID=community_id)
        community_name = community.name  # Store name for success message
        
        # Delete related events first
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM Events WHERE communityID = %s", [community_id])
        
        # Delete related community memberships (if any)
        CommunityMembership.objects.filter(communityID=community).delete()
        
        # Now delete the community
        community.delete()
        
        messages.success(request, f"Community '{community_name}' and its events have been successfully removed.")
    except Community.DoesNotExist:
        messages.error(request, "Community not found.")

    return redirect("admin_view")

@require_POST
@login_required
def remove_event(request):
    """ Remove an event after verifying the admin's password """
    event_id = request.POST.get("event_id")
    password = request.POST.get("password")

    # Verify the admin's password
    if not request.user.check_password(password):
        messages.error(request, "Incorrect password. Event removal cancelled.")
        return redirect("admin_view")

    # Check if the user is an Admin
    if request.user.Permission != "Admin":
        messages.error(request, "You do not have permission to remove events.")
        return redirect("admin_view")

    # Remove the event
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT eventTitle FROM Events WHERE eventID = %s", [event_id])
            event_title = cursor.fetchone()
            if not event_title:
                raise ValueError("Event not found")
            event_title = event_title[0]

            cursor.execute("DELETE FROM Events WHERE eventID = %s", [event_id])
        messages.success(request, f"Event '{event_title}' has been successfully removed.")
    except Exception:
        messages.error(request, "Event not found.")

    return redirect("admin_view")

@require_POST
@login_required
def review_community(request):
    request_id = request.POST.get("request_id")
    action = request.POST.get("action")
    note = request.POST.get("admin_note")
    password = request.POST.get("password")

    # Confirm password
    if not request.user.check_password(password):
        messages.error(request, "Incorrect password. Action cancelled.")
        return redirect("admin_view")

    with connection.cursor() as cursor:
        # Validate request exists and is still pending
        cursor.execute("SELECT name, communityDescription, communityCategory, requestedBy FROM CommunityRequests WHERE requestID = %s AND status = 'pending'", [request_id])
        data = cursor.fetchone()

        if not data:
            messages.error(request, "This request was already processed or not found.")
            return redirect("admin_view")

        name, description, category, requested_by = data

        if action == "approve":
            # Create community
            cursor.execute("""
                INSERT INTO Communities (name, communityDescription, communityCategory, createdBy, createdAt)
                VALUES (%s, %s, %s, %s, NOW())
            """, [name, description, category, requested_by])
            cursor.execute("SELECT LAST_INSERT_ID()")
            community_id = cursor.fetchone()[0]

            # Assign as admin
            cursor.execute("""
                INSERT INTO CommunityMemberships (communityID, userID, role, joinedAt)
                VALUES (%s, %s, 'Admin', NOW())
            """, [community_id, requested_by])

            status = 'approved'
            messages.success(request, f"Community '{name}' has been approved and created.")

        elif action == "reject":
            status = 'rejected'
            messages.info(request, f"Community '{name}' has been rejected.")

        else:
            messages.error(request, "Invalid action.")
            return redirect("admin_view")

        # Update request status and add note
        cursor.execute("""
            UPDATE CommunityRequests
            SET status = %s, reviewedBy = %s, reviewedAt = NOW(), adminNote = %s
            WHERE requestID = %s
        """, [status, request.user.userID, note, request_id])

    return redirect("admin_view")

def messages_view(request):
    return render(request, "profile/messages.html")

@login_required
def stream_user_token(request):
    client = get_stream_client()
    token = client.create_token(str(request.user.userID))
    return JsonResponse({
        "user_id": str(request.user.userID),
        "username": request.user.username,
        "token": token,
        "api_key": settings.STREAM_API_KEY,
    })

@login_required
def start_chat(request, target_id):
    try:
        current_user = request.user
        target_user = CustomUser.objects.get(userID=target_id)

        # Register both users on Stream (if not already)
        create_user_on_stream(current_user)
        create_user_on_stream(target_user)

        client = get_stream_client()
        members = sorted([str(current_user.userID), str(target_user.userID)])
        channel_id = f"dm-{members[0]}-{members[1]}"

        channel = client.channel("messaging", channel_id, {
            "members": members
        })

        channel.create(user_id=str(current_user.userID))

        # Send notification to the target user
        send_notification(
            user=target_user,
            message=f"{current_user.username} sent you a message",
            notification_type="message"
        )

        # 🛠️ Correct profile picture handling
        profile = Profile.objects.filter(user=target_user).first()
        profile_url = None
        if profile and profile.profile_picture:
            if str(profile.profile_picture).startswith("http"):
                # Already a Cloudinary full URL
                profile_url = str(profile.profile_picture)
            else:
                # Local upload, add domain
                profile_url = request.build_absolute_uri(profile.profile_picture.url)

        print("PROFILE URL SENT:", profile_url)

        return JsonResponse({
            "channel_id": channel.id,
            "username": target_user.username,
            "profile_picture": profile_url
        })

    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

@login_required
def chat_user_list(request):
    current_id = request.user.userID

    from django.db import connection

    domain = request.scheme + "://" + request.get_host()

    users = []

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.userID, u.username, p.profile_picture
            FROM User u
            LEFT JOIN Profiles p ON u.userID = p.userID
            WHERE u.userID != %s
        """, [current_id])
        rows = cursor.fetchall()

        for row in rows:
            user_id, username, profile_picture = row
            if profile_picture:
                if profile_picture.startswith("http"):
                    profile_url = profile_picture
                else:
                    profile_url = f"{domain}{settings.MEDIA_URL}{profile_picture}"
            else:
                profile_url = None

            users.append({
                "userID": user_id,
                "username": username,
                "profile_picture": profile_url
            })

    # Fetch communities
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.communityID, c.name
            FROM Communities c
            INNER JOIN CommunityMemberships m ON c.communityID = m.communityID
            WHERE m.userID = %s
        """, [current_id])
        communities = cursor.fetchall()

    community_chats = [{"communityID": str(cid), "name": name, "is_community": True} for cid, name in communities]

    return JsonResponse({
        "users": users,
        "communities": community_chats
    })

@login_required
def start_community_chat(request, community_id):
    current_user = request.user
    client = get_stream_client()

    # Fetch all members of the community
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT userID FROM CommunityMemberships WHERE communityID = %s
        """, [community_id])
        members = [str(row[0]) for row in cursor.fetchall()]

    # Register all users on Stream
    for uid in members:
        user = CustomUser.objects.get(userID=uid)
        create_user_on_stream(user)

    channel_id = f"community-{community_id}"
    channel = client.channel("messaging", channel_id, {
        "members": members
    })
    channel.create(user_id=str(current_user.userID))
    community = Community.objects.get(pk=community_id)
    return JsonResponse({"channel_id": channel.id,"name": community.name})

@login_required
def chat_community_list(request):
    user_id = request.user.userID
    memberships = CommunityMembership.objects.filter(userID=user_id).select_related("communityID")

    data = [
        {"communityID": m.communityID.communityID, "name": m.communityID.name}
        for m in memberships
    ]

    return JsonResponse(data, safe=False)

@login_required
@require_POST
def toggle_like(request):
    post_id = request.POST.get("post_id")
    post = get_object_or_404(Post, postID=post_id)
    user = request.user

    like, created = Like.objects.get_or_create(post=post, user=user)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        # Notify the post owner about the like
        if post.user != user:  # Don't notify if the user likes their own post
            send_notification(
                user=post.user,
                message=f"{user.username} liked your post",
                notification_type="like"
            )

    like_count = post.likes.count()
    return JsonResponse({"liked": liked, "like_count": like_count})

@require_POST
@login_required
def toggle_follow(request):
    target_id = request.POST.get("user_id")
    target_user = get_object_or_404(CustomUser, userID=target_id)

    if request.user == target_user:
        return JsonResponse({"error": "You cannot follow yourself."}, status=400)

    follow, created = Follow.objects.get_or_create(follower=request.user, following=target_user)

    if not created:
        return JsonResponse({"message": "Already following."}, status=200)

    # Notify the target user about the new follower
    send_notification(
        user=target_user,
        message=f"{request.user.username} started following you",
        notification_type="follow"
    )

    return JsonResponse({"message": "Followed successfully!"}, status=201)

@require_POST
@login_required
def toggle_unfollow(request):
    target_id = request.POST.get("user_id")
    target_user = get_object_or_404(CustomUser, userID=target_id)

    try:
        follow = Follow.objects.get(follower=request.user, following=target_user)
        follow.delete()
        return JsonResponse({"message": "Unfollowed successfully."}, status=200)
    except Follow.DoesNotExist:
        return JsonResponse({"error": "You are not following this user."}, status=400)

@login_required
def notifications_view(request):
    """Display all notifications for the logged-in user."""
    notifications = Notifications.objects.filter(userID=request.user).order_by('-createdAt')
    return render(request, 'notifications.html', {
        'notifications': notifications,
        'user_id': request.user.userID,
    })

@login_required
@require_POST
def mark_notification_read(request):
    """Mark a notification as read."""
    notification_id = request.POST.get('notification_id')
    try:
        notification = Notifications.objects.get(notificationID=notification_id, userID=request.user)
        notification.status = 'read'
        notification.save()
        return JsonResponse({'success': True})
    except Notifications.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)

@login_required
def post_detail(request, post_id):
    post = get_object_or_404(Post, postID=post_id)
    comments = post.comments.all().order_by('-created_at')
    form = CommentForm()

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.post = post
            comment.save()
            return redirect('post_detail', post_id=post_id)

    return render(request, 'posts/post_detail.html', {
        'post': post,
        'comments': comments,
        'form': form
    })

@login_required
def add_comment(request, post_id):
    if request.method == "POST":
        content = request.POST.get("content")
        post = get_object_or_404(Post, pk=post_id)

        if content:
            # Ensure request.user is resolved to a CustomUser instance
            user = request.user  # This should resolve the SimpleLazyObject
            if not isinstance(user, CustomUser):
                raise ValueError(f"Expected CustomUser instance, got {type(user)}")

            # Create the comment with the resolved user
            comment = Comment.objects.create(content=content, user=user, post=post)
            
            # Notify the post owner about the new comment
            if post.user != request.user:  # Avoid self-notification
                send_notification(
                    user=post.user,
                    message=f"{request.user.username} commented on your post",
                    notification_type="comment"
                )

        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('post_detail', post_id=post_id)  # Handle GET requests gracefully