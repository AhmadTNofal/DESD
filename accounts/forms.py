from django import forms
from django.contrib.auth.hashers import make_password
from .models import Community, Post, Profile, Comment, CustomUser

class SignupForm(forms.Form):
    username = forms.CharField(max_length=50)
    surname = forms.CharField(max_length=50)
    email = forms.EmailField()
    phoneNumber = forms.CharField(max_length=20)
    password = forms.CharField(widget=forms.PasswordInput)
    bio = forms.CharField(widget=forms.Textarea, required=False)
    major = forms.CharField(max_length=100, required=False)
    academicYear = forms.CharField(max_length=50, required=False)
    campusInvolvement = forms.CharField(widget=forms.Textarea, required=False)

    def clean_password(self):
        return make_password(self.cleaned_data["password"])

class CommunityForm(forms.ModelForm):
    """ Form to create a new community. """
    
    class Meta:
        model = Community
        fields = ["name", "communityDescription", "communityCategory"]
        labels = {
            "name": "Community Name",
            "communityDescription": "Description",
            "communityCategory": "Category",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter community name"}),
            "communityDescription": forms.Textarea(attrs={"class": "form-control", "placeholder": "Describe your community", "rows": 4}),
            "communityCategory": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter category (e.g., Sports, Tech, Music)"}),
        }

class EventForm(forms.Form):
    communityID = forms.IntegerField(label="Community ID")
    eventTitle = forms.CharField(max_length=100, label="Event Title")
    eventDate = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Event Date")
    eventTime = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label="Event Time")
    location = forms.CharField(max_length=255, required=False, label="Location")
    virtualLink = forms.CharField(max_length=255, required=False, label="Virtual Link")
    description = forms.CharField(widget=forms.Textarea, required=True)

class PostForm(forms.ModelForm):
    # tagging users field
    tagged_users = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),  # We'll set this dynamically in the view
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False,
        label="Tag Users"
    )

    class Meta:
        model = Post
        fields = ['image', 'content', 'tagged_users']  # Include tagged_users in the form
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Write something...', 'rows': 4}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the current user from the view
        super().__init__(*args, **kwargs)
        if user:
            # Only show users that the current user follows
            self.fields['tagged_users'].queryset = CustomUser.objects.filter(followers__follower=user).exclude(userID=user.userID)

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'major', 'academicYear', 'campusInvolvement', 'profile_picture']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Write a comment...'
            })
        }