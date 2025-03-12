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
from .models import CustomUser

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
                user_id = cursor.lastrowid

                # Insert into Profiles table
                cursor.execute("""
                    INSERT INTO Profiles (userID, bio, major, academicYear, campusInvolvement)
                    VALUES (%s, %s, %s, %s, %s)
                """, [user_id, bio, major, academicYear, campusInvolvement])

            messages.success(request, "Signup successful! Please login.")
            return redirect("login")  # Redirect to login page

        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    return render(request, 'registration/signup.html')