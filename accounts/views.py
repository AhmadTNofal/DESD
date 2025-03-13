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
                # Insert into User table
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

            messages.success(request, "Signup successful! Please login.")
            return redirect("login")  # Redirect to login page

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
    return render(request, 'profile/profile.html', {'user': request.user})


@login_required
def edit_profile(request):
    if request.method == "POST":
        user = request.user  # Get the logged-in user

        # Debugging: Print user attributes to confirm correct field names
        print(f"User Object: {user.__dict__}")

        if not hasattr(user, 'userID'):  # Ensure userID exists
            print("❌ Error: User object does not have 'userID'")
            messages.error(request, "Error: User object does not have 'userID'")
            return redirect("profile_settings")

        # Update user fields
        user.username = request.POST["username"]
        user.email = request.POST["email"]
        user.surname = request.POST.get("surname", "")
        user.phoneNumber = request.POST.get("phoneNumber", "")

        try:
            user.save()  # ✅ Save user data using Django ORM
            print("✅ Profile updated successfully!")
            messages.success(request, "Profile updated successfully!")
        except Exception as e:
            print(f"❌ Error: {e}")  # Debugging
            messages.error(request, f"Error updating profile: {e}")

    return redirect("profile_settings")


def events(request):
    return render(request, 'Events/events.html')

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


