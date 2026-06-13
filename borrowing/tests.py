from datetime import timedelta
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from books.models import Book
from borrowing.models import Borrow


class BorrowingSystemTests(TestCase):
    def setUp(self):
        # Create user accounts
        self.member_user = CustomUser.objects.create_user(
            username="member_user",
            email="member@library.com",
            password="password123",
            role=CustomUser.Role.MEMBER,
        )
        self.other_member_user = CustomUser.objects.create_user(
            username="other_member",
            email="other@library.com",
            password="password123",
            role=CustomUser.Role.MEMBER,
        )
        self.admin_user = CustomUser.objects.create_user(
            username="admin_user",
            email="admin@library.com",
            password="password123",
            role=CustomUser.Role.ADMIN,
        )

        # Create books
        self.book_in_stock = Book.objects.create(
            title="Design Patterns",
            author="Erich Gamma",
            genre="Computer Science",
            publish_year=1994,
            isbn="978-0201633610",
            total_copies=2,
            available_copies=2,
        )
        self.book_out_of_stock = Book.objects.create(
            title="Refactoring",
            author="Martin Fowler",
            genre="Computer Science",
            publish_year=1999,
            isbn="978-0201485677",
            total_copies=1,
            available_copies=0,
        )

        # Setup URLs
        self.list_url = reverse("borrowing:borrow_list")
        self.history_url = reverse("borrowing:borrow_history")
        self.borrow_stock_url = reverse("borrowing:borrow_book", kwargs={"book_id": self.book_in_stock.pk})
        self.borrow_out_url = reverse("borrowing:borrow_book", kwargs={"book_id": self.book_out_of_stock.pk})

    def test_default_due_date_calculation(self):
        self.client.login(username="member_user", password="password123")
        self.client.post(self.borrow_stock_url)
        
        borrow = Borrow.objects.get(book=self.book_in_stock, user=self.member_user)
        # Verify due date is default 14 days after borrow date
        expected_due = borrow.borrow_date + timedelta(days=14)
        self.assertAlmostEqual(borrow.due_date, expected_due, delta=timedelta(seconds=2))

    def test_successful_borrow_decrements_available_copies(self):
        self.client.login(username="member_user", password="password123")
        
        # Verify initial count
        self.assertEqual(self.book_in_stock.available_copies, 2)
        
        # Borrow book
        response = self.client.post(self.borrow_stock_url)
        self.assertRedirects(response, self.list_url)
        
        # Verify copy count decremented
        self.book_in_stock.refresh_from_db()
        self.assertEqual(self.book_in_stock.available_copies, 1)
        
        # Verify Borrow object created with correct status
        self.assertTrue(Borrow.objects.filter(book=self.book_in_stock, user=self.member_user, status=Borrow.StatusChoices.BORROWED).exists())

    def test_cannot_borrow_out_of_stock_book(self):
        self.client.login(username="member_user", password="password123")
        
        # Attempt to borrow out of stock book
        response = self.client.post(self.borrow_out_url)
        self.assertRedirects(response, reverse("books:book_detail", kwargs={"pk": self.book_out_of_stock.pk}))
        
        # Verify no Borrow record created
        self.assertFalse(Borrow.objects.filter(book=self.book_out_of_stock, user=self.member_user).exists())
        
        # Verify error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("out of stock", str(messages[0]))

    def test_successful_return_increments_available_copies(self):
        # Setup pre-existing borrow
        borrow = Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            due_date=timezone.now() + timedelta(days=14)
        )
        self.book_in_stock.available_copies = 1
        self.book_in_stock.save()
        
        self.client.login(username="member_user", password="password123")
        return_url = reverse("borrowing:return_book", kwargs={"pk": borrow.pk})
        
        # Return book
        response = self.client.post(return_url)
        self.assertRedirects(response, self.list_url)
        
        # Verify status is returned and return date is set
        borrow.refresh_from_db()
        self.assertEqual(borrow.status, Borrow.StatusChoices.RETURNED)
        self.assertIsNotNone(borrow.return_date)
        
        # Verify copies incremented
        self.book_in_stock.refresh_from_db()
        self.assertEqual(self.book_in_stock.available_copies, 2)

    def test_member_only_sees_own_borrowings_in_list(self):
        # Create borrowing for both users
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            due_date=timezone.now() + timedelta(days=14)
        )
        Borrow.objects.create(
            user=self.other_member_user,
            book=self.book_out_of_stock,
            due_date=timezone.now() + timedelta(days=14)
        )
        
        # Log in as member_user
        self.client.login(username="member_user", password="password123")
        response = self.client.get(self.list_url)
        
        # Verify member_user only sees their own
        self.assertEqual(len(response.context["borrowings"]), 1)
        self.assertEqual(response.context["borrowings"][0].user, self.member_user)

    def test_librarian_sees_all_borrowings_in_list(self):
        # Create borrowing for both users
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            due_date=timezone.now() + timedelta(days=14)
        )
        Borrow.objects.create(
            user=self.other_member_user,
            book=self.book_out_of_stock,
            due_date=timezone.now() + timedelta(days=14)
        )
        
        # Log in as librarian
        self.client.login(username="admin_user", password="password123")
        response = self.client.get(self.list_url)
        
        # Verify librarian sees both records
        self.assertEqual(len(response.context["borrowings"]), 2)

    def test_history_active_filter(self):
        # Create active borrow
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            due_date=timezone.now() + timedelta(days=14)
        )
        # Create returned borrow
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_out_of_stock,
            status=Borrow.StatusChoices.RETURNED,
            due_date=timezone.now() - timedelta(days=1),
            return_date=timezone.now()
        )
        
        self.client.login(username="member_user", password="password123")
        response = self.client.get(self.history_url, {"status": "active"})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["borrowings"]), 1)
        self.assertEqual(response.context["borrowings"][0].book, self.book_in_stock)

    def test_history_returned_filter(self):
        # Create active borrow
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            due_date=timezone.now() + timedelta(days=14)
        )
        # Create returned borrow
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_out_of_stock,
            status=Borrow.StatusChoices.RETURNED,
            due_date=timezone.now() - timedelta(days=1),
            return_date=timezone.now()
        )
        
        self.client.login(username="member_user", password="password123")
        response = self.client.get(self.history_url, {"status": "returned"})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["borrowings"]), 1)
        self.assertEqual(response.context["borrowings"][0].book, self.book_out_of_stock)

    def test_history_overdue_filter(self):
        # Create active, not overdue borrow
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            due_date=timezone.now() + timedelta(days=14)
        )
        # Create active, overdue borrow (due_date in past)
        Borrow.objects.create(
            user=self.member_user,
            book=self.book_out_of_stock,
            status=Borrow.StatusChoices.BORROWED,
            due_date=timezone.now() - timedelta(days=5)
        )
        
        self.client.login(username="member_user", password="password123")
        response = self.client.get(self.history_url, {"status": "overdue"})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["borrowings"]), 1)
        self.assertEqual(response.context["borrowings"][0].book, self.book_out_of_stock)
