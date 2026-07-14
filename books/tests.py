from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from books.models import Book


class BookDeleteViewTests(TestCase):
    def setUp(self):
        # Create standard metadata fields required by Book model validation
        self.book = Book.objects.create(
            title="Django 5 Development",
            author="John Doe",
            genre="Technology",
            publish_year=2024,
            isbn="1234567890123",
            total_copies=5,
            available_copies=5,
        )
        self.delete_url = reverse("books:book_delete", kwargs={"pk": self.book.pk})

        self.member_user = CustomUser.objects.create_user(
            username="member_user",
            email="member@library.com",
            password="password123",
            role=CustomUser.Role.MEMBER,
        )

        self.admin_user = CustomUser.objects.create_user(
            username="admin_user",
            email="admin@library.com",
            password="password123",
            role=CustomUser.Role.ADMIN,
        )

    def test_anonymous_cannot_delete_book(self):
        # GET request should redirect to login
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

        # POST request should redirect to login and not delete the book
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_member_cannot_delete_book(self):
        self.client.login(username="member_user", password="password123")

        # GET request should be forbidden
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 403)

        # POST request should be forbidden and not delete the book
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_admin_can_access_delete_confirmation_page(self):
        self.client.login(username="admin_user", password="password123")

        # GET request should succeed
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "books/book_confirm_delete.html")
        self.assertContains(response, self.book.title)

    def test_admin_can_delete_book(self):
        self.client.login(username="admin_user", password="password123")

        # POST request should delete the book and redirect
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, reverse("books:book_list"))

        # Verify book is deleted
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())

        # Verify success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Book deleted successfully.")
