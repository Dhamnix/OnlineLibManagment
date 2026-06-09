from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


User = get_user_model()


class BootstrapFormMixin:
    """Apply Bootstrap classes in one place for consistent auth forms."""

    def _apply_bootstrap_classes(self):
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()


class CustomUserRegistrationForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_classes()
        self.fields["username"].widget.attrs.update({"placeholder": "Choose a username"})
        self.fields["email"].widget.attrs.update({"placeholder": "you@example.com"})
        self.fields["first_name"].widget.attrs.update({"placeholder": "First name"})
        self.fields["last_name"].widget.attrs.update({"placeholder": "Last name"})
        self.fields["password1"].widget.attrs.update({"placeholder": "Create a password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm password"})

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email


class BootstrapAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """AuthenticationForm already validates username/password correctly."""

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self._apply_bootstrap_classes()
        self.fields["username"].widget.attrs.update({"placeholder": "Username"})
        self.fields["password"].widget.attrs.update({"placeholder": "Password"})
