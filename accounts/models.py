from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, User
from django.db import models

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

    class Meta:
        db_table = "Profiles"  # Match the exact MySQL table name
        managed = False  # Since MySQL manages this table

    def __str__(self):
        return f"{self.user.username}'s Profile"


