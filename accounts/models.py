from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, User
from django.db import models
from django.conf import settings
from django.db import models
from django.conf import settings

class CustomUserManager(BaseUserManager):
    """ Manager for CustomUser to handle user creation properly. """

    def create_user(self, username, surname, email, phoneNumber, password=None):
        """ Create and return a regular user with a hashed password. """
        if not username:
            raise ValueError("Users must have a username")
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            username=username,
            surname=surname,
            email=email,
            phoneNumber=phoneNumber,
        )
        user.set_password(password)  # Hash password before storing
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser):
    """ Custom user model for authentication, mapping to the 'User' table. """

    userID = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    surname = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, unique=True)
    phoneNumber = models.CharField(max_length=20)
    password = models.CharField(max_length=255)  
    createdAt = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    Permission = models.CharField(max_length=255)  

    objects = CustomUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "surname", "phoneNumber"]

    def __str__(self):
        return self.username

    @property
    def is_active(self):
        return True

    @property
    def is_staff(self):
        return self.Permission == "Admin"

    class Meta:
        db_table = 'User'
        managed = False  # Since MySQL manages this table

class Community(models.Model):
    """ Model representing a community. """
    communityID = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    communityDescription = models.TextField(blank=True, null=True)
    communityCategory = models.CharField(max_length=100, blank=True, null=True)
    createdBy = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column="createdBy")  
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Communities"  # Match the database table name
        managed = False  # Since MySQL manages this table

    def __str__(self):
        return self.name

class CommunityMembership(models.Model):
    """ Model for managing user memberships in communities. """
    membershipID = models.AutoField(primary_key=True)
    communityID = models.ForeignKey(Community, on_delete=models.CASCADE, db_column="communityID") 
    userID = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column="userID")  
    role = models.CharField(max_length=50, default="Member")
    joinedAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CommunityMemberships"  # Match the database table name
        managed = False  # Since MySQL manages this table

class Profile(models.Model):
    profileID = models.AutoField(primary_key=True)  # Explicitly define the primary key
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, db_column="userID")  # Ensure correct linking
    bio = models.TextField(blank=True, null=True)
    major = models.CharField(max_length=100, blank=True, null=True)
    academicYear = models.IntegerField(blank=True, null=True)
    campusInvolvement = models.TextField(blank=True, null=True)
    interests = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile_pics/", default="profile_pics/default.jpg")
    # Add to Profile model
    date_of_birth = models.DateField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    street_name = models.CharField(max_length=100, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = "Profiles"  # Match the exact MySQL table name
        managed = False  # Since MySQL manages this table

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Post(models.Model):
    postID = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        db_column="userID"
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        db_column="communityID",
        null=True,
        blank=True
    )

    # Add this:
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('community', 'Community Only')
    ]
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='public'
    )

    content = models.TextField()
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Posts"
        managed = False  # Since you're using a pre-existing table

    def __str__(self):
        return f"Post {self.postID} by {self.user.username}"

    def is_liked_by(self, user):
        return self.likes.filter(user=user).exists()

    def tagged_users(self):
        # Corrected query: Filter CustomUser using the related_name 'tagged_in_posts'
        return CustomUser.objects.filter(tagged_in_posts__post=self)

def user_directory_path(instance, filename):
    """Upload images to 'media/profile_pics/user_<id>/<filename>'"""
    return f'profile_pics/user_{instance.user.id}/{filename}'

class CommunityRequest(models.Model):
    requestID = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    communityDescription = models.TextField(null=True, blank=True)
    communityCategory = models.CharField(max_length=100, null=True, blank=True)
    requestedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='requestedBy', related_name='community_requests'
    )
    requestedAt = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    reviewedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='reviewedBy', related_name='reviewed_requests'
    )
    reviewedAt = models.DateTimeField(null=True, blank=True)
    adminNote = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "CommunityRequests"

class Like(models.Model):
    likeID = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, db_column='postID', related_name='likes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column='userID')

    class Meta:
        db_table = "Likes"
        managed = False  # Because you're managing the table manually

class Comment(models.Model):
    content = models.TextField()
    createdAt = models.DateTimeField(db_column='createdAt', auto_now_add=True)
    updatedAt = models.DateTimeField(db_column='updatedAt', auto_now=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments')

    def __str__(self):
        return f"{self.user.username} on {self.post.postID}"

    class Meta:
        db_table = "accounts_comment"
        managed = False

class Follow(models.Model):
    follower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        db_table = "accounts_follow"
        managed = False

class Notifications(models.Model):
    notificationID = models.AutoField(primary_key=True)
    userID = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column="userID")
    message = models.TextField()
    type = models.CharField(max_length=50)  # e.g., "post", "follow", "message", "event", "community", "like"
    status = models.CharField(max_length=20, default="unread")  # "unread" or "read"
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Notifications"
        managed = False

    def __str__(self):
        return f"Notification for {self.userID.username}: {self.message}"

class EventRegistration(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    event = models.ForeignKey('Events', on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "EventRegistrations"
        managed = False

class NotificationPreferences(models.Model):
    preferenceID = models.AutoField(primary_key=True)
    userID = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column="userID")
    email_post = models.BooleanField(default=True)
    email_follow = models.BooleanField(default=True)
    email_message = models.BooleanField(default=True)
    email_event = models.BooleanField(default=True)
    email_community = models.BooleanField(default=True)
    email_like = models.BooleanField(default=True)
    in_app_post = models.BooleanField(default=True)
    in_app_follow = models.BooleanField(default=True)
    in_app_message = models.BooleanField(default=True)
    in_app_event = models.BooleanField(default=True)
    in_app_community = models.BooleanField(default=True)
    in_app_like = models.BooleanField(default=True)

    class Meta:
        db_table = "NotificationPreferences"
        managed = False

    def __str__(self):
        return f"Preferences for {self.userID.username}"

class PostTags(models.Model):
    postTagID = models.AutoField(primary_key=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='posttags', db_column='postID')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tagged_in_posts', db_column='userID')

    class Meta:
        db_table = "PostTags"
        managed = False
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user.username} tagged in Post {self.post.postID}"