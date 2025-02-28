from django.db import models

class CustomUser(models.Model):
    userID = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    email = models.EmailField(max_length=100)
    phoneNumber = models.CharField(max_length=20)
    password = models.CharField(max_length=255)
    createdAt = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Properties to satisfy Django's authentication system:
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_staff(self):
        return False

    @property
    def is_superuser(self):
        return False

    def get_username(self):
        return self.username

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'User'
        managed = False 
