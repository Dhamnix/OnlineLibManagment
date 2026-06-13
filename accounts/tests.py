from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser


class AuthenticationTests(TestCase):
    def setUp(self):
        self.register_url = reverse("accounts:register")
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")
        self.profile_url = reverse("accounts:profile")

        self.user_data = {
            "username": "new_user",
            "email": "new_user@example.com",
            "first_name": "New",
            "last_name": "User",
            "role": "MEMBER",
            "password1": "securepass123",
            "password2": "securepass123",
        }

    def test_register_member_success_and_auto_login(self):
        # Post valid registration data for MEMBER
        response = self.client.post(self.register_url, self.user_data)
        
        # Verify redirect to profile
        self.assertRedirects(response, self.profile_url)
        
        # Verify user is created in database with MEMBER role
        user = CustomUser.objects.get(username="new_user")
        self.assertEqual(user.role, CustomUser.Role.MEMBER)
        
        # Verify user is logged in
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        
        # Verify success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Your account has been created successfully.")

    def test_register_librarian_success_and_auto_login(self):
        # Post valid registration data for ADMIN (Librarian)
        data = self.user_data.copy()
        data["role"] = "ADMIN"
        data["username"] = "new_librarian"
        data["email"] = "librarian@example.com"
        
        response = self.client.post(self.register_url, data)
        
        self.assertRedirects(response, self.profile_url)
        
        # Verify user role is ADMIN
        user = CustomUser.objects.get(username="new_librarian")
        self.assertEqual(user.role, CustomUser.Role.ADMIN)
        
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_success(self):
        # Create a user to log in
        user = CustomUser.objects.create_user(
            username="existing_user",
            email="existing@example.com",
            password="testpassword123",
            role=CustomUser.Role.MEMBER,
        )
        
        # Post valid login credentials
        response = self.client.post(
            self.login_url,
            {"username": "existing_user", "password": "testpassword123"},
        )
        
        self.assertRedirects(response, self.profile_url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        # Verify success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You are now logged in.")

    def test_login_invalid_credentials(self):
        # Post invalid login credentials
        response = self.client.post(
            self.login_url,
            {"username": "wrong_user", "password": "wrongpassword"},
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)
        
        # Verify error message is in context or messages
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Invalid username or password.")

    def test_logout_success(self):
        # Create a user and log in
        user = CustomUser.objects.create_user(
            username="test_logout_user",
            email="logout@example.com",
            password="testpassword123",
            role=CustomUser.Role.MEMBER,
        )
        self.client.login(username="test_logout_user", password="testpassword123")
        
        # POST request to logout
        response = self.client.post(self.logout_url)
        
        # Verify redirection to login page
        self.assertRedirects(response, self.login_url)
        self.assertFalse("_auth_user_id" in self.client.session)
        
        # Verify logout success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You have been logged out.")
