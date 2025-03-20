from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db import connection
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from .models import CustomUser, Community, CommunityMembership, Profile
from .forms import CommunityForm, EventForm
from django.urls import reverse
from datetime import date
from .models import Post 
from .forms import PostForm 
from django.core.files.storage import default_storage 

@login_required
def home(request):
    """Render the home page after successful login."""
    return render(request, "profile/home.html", {"permission": request.user.Permission})
def search_page(request):
    return render(request, "profile/search.html")
def search_users(request):
    """ Allow users to search for others by username, email, or surname """
    
    query = request.GET.get('q', '').strip() # Get the search query from the request and remove whitespace
    
    results = CustomUser.objects.filter(
        Q(username__icontains=query) | 
        Q(email__icontains=query) | 
        Q(surname__icontains=query)
    ) if query else None  # Return None if query is empty

    return render(request, 'profile/search_results.html', {'results': results, 'query': query}) 

def search_communities(request):
    """ Allow users to search for communities by name or category """
    
    query = request.GET.get('q', '').strip()  # Get search query

    results = Community.objects.filter(
        Q(name__icontains=query) | 
        Q(communityCategory__icontains=query)
    ) if query else None  # Return results only if query is not empty

    return render(request, 'Communities/search_communities.html', {'results': results, 'query': query})

def search_events(request):
    """ Allow users to search for events by title, location, or community name """
    
    query = request.GET.get('q', '').strip()  # Get search query

    results = []
    if query:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, c.name as communityName
                FROM Events e
                JOIN Communities c ON e.communityID = c.communityID
                WHERE e.eventTitle LIKE %s OR e.location LIKE %s OR c.name LIKE %s
            """, [f"%{query}%", f"%{query}%", f"%{query}%"])
            
            results = cursor.fetchall()  # Fetch raw query results

    return render(request, 'Events/search_events.html', {'results': results, 'query': query})

def view_profile(request, user_id):
    """ Display full profile of a user. """
    user = CustomUser.objects.get(userID=user_id)  # Fetch user by ID
    return render(request, 'profile/view_profile.html', {'user': user})

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
                    INSERT INTO `Profiles` (userID, bio, major, academicYear, campusInvolvement)
                    VALUES (%s, %s, %s, %s, %s)
                """, [user_id, bio, major, academicYear, campusInvolvement])

            # ✅ Authenticate and Log in the user
            user = CustomUser.objects.get(userID=user_id)  # Get the newly created user
            user.backend = 'django.contrib.auth.backends.ModelBackend'  # Required to log in manually
            login(request, user)  # Log the user in

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
    """ Handles the creation of a new community. """
    if request.method == "POST":
        form = CommunityForm(request.POST)
        if form.is_valid():
            community = form.save(commit=False)
            community.createdBy = request.user  # Assign the logged-in user as creator
            community.save()

            # Assign creator as "Admin" in CommunityMemberships
            CommunityMembership.objects.create(
                communityID=community,
                userID=request.user,
                role="Admin"
            )

            messages.success(request, "Community created successfully!")
            return redirect("communities")  # Redirect to communities page
        else:
            print("Form Errors:", form.errors)  # Debugging: Print errors to console
            messages.error(request, "Error creating community. Please check the form.")

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

        # ✅ Handle Profile Picture Upload
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

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
    """ Fetch and display event details """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, e.description, c.name as communityName
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
        "communityName": event[6]
    }

    return render(request, "Events/event_details.html", {"event": event_data})
@login_required
def create_event(request):
    user_id = request.user.userID  # Get logged-in user ID

    # Fetch communities where the user is an admin
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
            community_id = request.POST.get("communityID")  # Get selected community ID
            is_online = request.POST.get("onlineEvent")  # Check if online checkbox is selected

            location = data['location'] if not is_online else None
            virtual_link = data['virtualLink'] if is_online else None
            description = data['description']

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO Events (communityID, eventTitle, eventDate, eventTime, location, virtualLink, description, createdBy, createdAt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [community_id, data['eventTitle'], data['eventDate'], data['eventTime'], location, virtual_link, description, user_id]
                )
            return redirect('events')  # Redirect to events list after creation
    else:
        form = EventForm()

    return render(request, 'Events/create_event.html', {'form': form, 'communities': communities})


@login_required
def change_event(request):
    user_id = request.user.userID  # Get logged-in user ID

    # Fetch all events created by the user
    with connection.cursor() as cursor:
        cursor.execute("SELECT eventID, eventTitle FROM Events WHERE createdBy = %s", [user_id])
        events = cursor.fetchall()  # List of (eventID, eventTitle)

    selected_event = None  # Stores selected event details

    if request.method == "POST":
        event_id = request.POST.get("eventID")

        # If an event is selected, fetch its details
        if event_id:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT eventID, eventTitle, eventDate, eventTime, location, virtualLink, description FROM Events WHERE eventID = %s AND createdBy = %s",
                    [event_id, user_id]
                )
                selected_event = cursor.fetchone()

        # If the form is submitted with updates, save changes
        if "updateEvent" in request.POST:
            eventTitle = request.POST.get("eventTitle")
            eventDate = request.POST.get("eventDate")
            eventTime = request.POST.get("eventTime")
            location = request.POST.get("location") if "onlineEvent" not in request.POST else None
            virtualLink = request.POST.get("virtualLink") if "onlineEvent" in request.POST else None
            description = request.POST.get("description")

            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE Events SET eventTitle=%s, eventDate=%s, eventTime=%s, location=%s, virtualLink=%s, description=%s WHERE eventID=%s",
                    [eventTitle, eventDate, eventTime, location, virtualLink, description, event_id]
                )

            return redirect('change_events')  # Refresh page after update

    return render(request, 'Events/change_event.html', {'events': events, 'selected_event': selected_event})

@login_required
def cancel_event(request):
    user_id = request.user.userID  # Get logged-in user ID

    # Fetch all events created by the user
    with connection.cursor() as cursor:
        cursor.execute("SELECT eventID, eventTitle FROM Events WHERE createdBy = %s", [user_id])
        events = cursor.fetchall()  # List of (eventID, eventTitle)

    if request.method == "POST":
        event_id = request.POST.get("eventID")

        # If an event is selected, delete it
        if event_id:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM Events WHERE eventID = %s AND createdBy = %s", [event_id, user_id])

            return redirect('cancel_events')  # Refresh the page after deletion

    return render(request, 'Events/cancel_event.html', {'events': events})

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

        messages.success(request, "You have successfully joined the community!")

    # Redirect back to the same page the user came from
    return redirect(request.META.get('HTTP_REFERER', 'communities'))

@login_required
def create_post(request):
    """ Allow logged-in users to create a post """
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user  # Assign the logged-in user as the author
            post.save()
            messages.success(request, "Post created successfully!")
            return redirect("home")  # Redirect back to homepage
    else:
        form = PostForm()

    return render(request, "profile/create_post.html", {"form": form})
