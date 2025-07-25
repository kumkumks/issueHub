from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password, password_validators_help_text_html
from .models import User

class AccountCreationForm(forms.Form):
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    first_name = forms.CharField(max_length=255)
    last_name = forms.CharField(max_length=255)
    password = forms.CharField(
        widget=forms.PasswordInput,
        help_text=password_validators_help_text_html()
    )
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if User.objects.filter(phone=phone).exists():
            raise ValidationError('A user with this phone number already exists.')
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

class OrganisationCreationForm(forms.Form):
    name = forms.CharField(max_length=255)
    address = forms.CharField(widget=forms.Textarea, required=False)

class UserLoginForm(forms.Form):
    email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if not email or not password:
            raise forms.ValidationError('Both email and password are required.')
        return cleaned_data

class GeneralUserLoginForm(forms.Form):
    phone = forms.CharField(label='Phone Number', max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get('phone')
        if not phone:
            raise forms.ValidationError('Phone number is required.')
        return cleaned_data