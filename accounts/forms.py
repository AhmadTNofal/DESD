from django import forms
from django.contrib.auth.hashers import make_password

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
