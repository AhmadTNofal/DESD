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
from .models import CustomUser, Community, CommunityMembership
from .forms import CommunityForm, EventForm
from django.urls import reverse
from datetime import date

@login_required
def home(request):
    """Render the home page after successful login."""
    return render(request, "profile/home.html", {"permission": request.user.Permission})

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



def communities(request):
    return render(request, 'Communities/community.html')

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




from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Profile  # Import Profile model

@login_required
def edit_profile(request):
    user = request.user  # Get logged-in user
    profile = Profile.objects.filter(user=user).first()

    if not profile:
        messages.error(request, "Profile not found.")
        return redirect("profile_settings")

    if request.method == "POST":
        # Update User Model Fields
        user.username = request.POST["username"]
        user.email = request.POST["email"]
        user.surname = request.POST.get("surname", "")
        user.phoneNumber = request.POST.get("phoneNumber", "")

        # Update Profile Model Fields
        profile.bio = request.POST.get("bio", profile.bio)
        profile.major = request.POST.get("major", profile.major)
        profile.academicYear = request.POST.get("academicYear", profile.academicYear)
        profile.campusInvolvement = request.POST.get("campusInvolvement", profile.campusInvolvement)

        try:
            user.save()  # Save User Data
            profile.save()  # Save Profile Data
            messages.success(request, "Profile updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")

        return redirect("profile_settings")

    return render(request, "profile/profile.html", {"user": user, "profile": profile})






def events(request):
    """ Fetch and filter events based on user input and include available locations """
    query = request.GET.get("q", "").strip()
    selected_date = request.GET.get("date", "")
    selected_time = request.GET.get("time", "")
    online_filter = request.GET.get("online", "")
    location_filter = request.GET.get("location", "")

    if request.user.is_authenticated:
        user_id = request.user.userID  # FIXED: Use 'userID' instead of 'id'
    else:
        user_id = None  # Handle unauthenticated users

    # Fetch only events from communities the user is part of
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.eventID, e.eventTitle, e.eventDate, e.eventTime, e.location, e.virtualLink, c.name as communityName
            FROM Events e
            JOIN Communities c ON e.communityID = c.communityID
            JOIN CommunityMemberships cm ON cm.communityID = c.communityID
            WHERE e.eventDate >= %s AND cm.userID = %s
        """, [date.today(), user_id])

        events = cursor.fetchall()

    # Fetch distinct locations for filtering
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT location FROM Events WHERE location IS NOT NULL ORDER BY location")
        locations = [row[0] for row in cursor.fetchall()]  # Extract locations from query result

    # Convert raw data into dictionaries
    filtered_events = []
    for event in events:
        event_id, title, event_date, event_time, location, virtual_link, community_name = event

        event_data = {
            "eventID": event_id,
            "eventTitle": title,
            "eventDate": event_date,
            "eventTime": event_time.strftime("%H:%M"),
            "location": location,
            "virtualLink": virtual_link,
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
        "locations": locations,  # FIXED: Passing locations to the template
        "query": query
    })

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

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO Events (communityID, eventTitle, eventDate, eventTime, location, virtualLink, createdBy, createdAt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    [community_id, data['eventTitle'], data['eventDate'], data['eventTime'], location, virtual_link, user_id]
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
                    "SELECT eventID, eventTitle, eventDate, eventTime, location, virtualLink FROM Events WHERE eventID = %s AND createdBy = %s",
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

            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE Events SET eventTitle=%s, eventDate=%s, eventTime=%s, location=%s, virtualLink=%s WHERE eventID=%s",
                    [eventTitle, eventDate, eventTime, location, virtualLink, event_id]
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