from datetime import timedelta
from decimal import Decimal
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from accounts.models import CustomUser
from books.models import Book
from borrowing.models import Borrow, Reservation, Fine
from borrowing.services import calculate_fine_for_borrow, create_or_update_fine_for_borrow


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
            isbn="9780201633610",
            total_copies=2,
            available_copies=2,
        )
        self.book_out_of_stock = Book.objects.create(
            title="Refactoring",
            author="Martin Fowler",
            genre="Computer Science",
            publish_year=1999,
            isbn="9780201485677",
            total_copies=1,
            available_copies=0,
        )

        # Setup URLs
        self.list_url = reverse("borrowing:borrow_list")
        self.history_url = reverse("borrowing:borrow_history")
        self.reservations_list_url = reverse("borrowing:reservation_list")
        self.fines_list_url = reverse("borrowing:fine_list")
        self.borrow_stock_url = reverse("borrowing:request_borrow", kwargs={"book_id": self.book_in_stock.pk})
        self.borrow_out_url = reverse("borrowing:request_borrow", kwargs={"book_id": self.book_out_of_stock.pk})
        self.reserve_stock_url = reverse("borrowing:reserve_book", kwargs={"book_id": self.book_in_stock.pk})
        self.reserve_out_url = reverse("borrowing:reserve_book", kwargs={"book_id": self.book_out_of_stock.pk})

    def test_default_due_date_calculation(self):
        self.client.login(username="member_user", password="password123")
        self.client.post(self.borrow_stock_url)
        
        borrow = Borrow.objects.get(book=self.book_in_stock, user=self.member_user)
        self.assertIsNone(borrow.due_date)
        
        # Approve as admin
        self.client.login(username="admin_user", password="password123")
        approve_url = reverse("borrowing:approve_borrow", kwargs={"pk": borrow.pk})
        self.client.post(approve_url, {"loan_days": 14})
        
        borrow.refresh_from_db()
        self.assertEqual(borrow.status, Borrow.StatusChoices.BORROWED)
        expected_due = borrow.borrow_date + timedelta(days=14)
        self.assertAlmostEqual(borrow.due_date, expected_due, delta=timedelta(seconds=2))

    def test_successful_borrow_decrements_available_copies(self):
        self.client.login(username="member_user", password="password123")
        
        # Verify initial count
        self.assertEqual(self.book_in_stock.available_copies, 2)
        
        # Borrow request (PENDING)
        response = self.client.post(self.borrow_stock_url)
        self.assertRedirects(response, self.list_url)
        
        # Verify copies not decremented yet
        self.book_in_stock.refresh_from_db()
        self.assertEqual(self.book_in_stock.available_copies, 2)
        
        borrow = Borrow.objects.get(book=self.book_in_stock, user=self.member_user)
        self.assertEqual(borrow.status, Borrow.StatusChoices.PENDING)
        
        # Approve as admin
        self.client.login(username="admin_user", password="password123")
        approve_url = reverse("borrowing:approve_borrow", kwargs={"pk": borrow.pk})
        response = self.client.post(approve_url, {"loan_days": 14})
        self.assertRedirects(response, reverse("borrowing:admin_borrow_requests"))
        
        # Verify copy count decremented after approval
        self.book_in_stock.refresh_from_db()
        self.assertEqual(self.book_in_stock.available_copies, 1)

    def test_cannot_borrow_out_of_stock_book(self):
        self.client.login(username="member_user", password="password123")
        
        # Attempt to request borrow out of stock book
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
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        self.book_in_stock.available_copies = 1
        self.book_in_stock.save()
        
        # Non-admin user attempts to return -> forbidden / redirect to list
        self.client.login(username="member_user", password="password123")
        return_url = reverse("borrowing:return_book", kwargs={"pk": borrow.pk})
        response = self.client.post(return_url)
        self.assertRedirects(response, self.list_url)
        
        # Verify status is still borrowed
        borrow.refresh_from_db()
        self.assertEqual(borrow.status, Borrow.StatusChoices.BORROWED)
        
        # Admin user returns book
        self.client.login(username="admin_user", password="password123")
        response = self.client.post(return_url)
        self.assertRedirects(response, reverse("borrowing:admin_borrow_list"))
        
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

    def test_cannot_reserve_in_stock_book(self):
        self.client.login(username="member_user", password="password123")
        
        # Attempt to reserve an in-stock book
        response = self.client.post(self.reserve_stock_url)
        self.assertRedirects(response, reverse("books:book_detail", kwargs={"pk": self.book_in_stock.pk}))
        
        # Verify no Reservation record created
        self.assertFalse(Reservation.objects.filter(book=self.book_in_stock, user=self.member_user).exists())

    def test_reserve_out_of_stock_book(self):
        self.client.login(username="member_user", password="password123")
        
        # Reserve out of stock book
        response = self.client.post(self.reserve_out_url)
        self.assertRedirects(response, self.reservations_list_url)
        
        # Verify Reservation is created with PENDING status
        self.assertTrue(Reservation.objects.filter(book=self.book_out_of_stock, user=self.member_user, status=Reservation.StatusChoices.PENDING).exists())

    def test_returning_book_notifies_oldest_reservation(self):
        # Create reservations
        res_oldest = Reservation.objects.create(
            user=self.member_user,
            book=self.book_out_of_stock,
            status=Reservation.StatusChoices.PENDING,
            reservation_date=timezone.now() - timedelta(hours=2)
        )
        res_newest = Reservation.objects.create(
            user=self.other_member_user,
            book=self.book_out_of_stock,
            status=Reservation.StatusChoices.PENDING,
            reservation_date=timezone.now() - timedelta(hours=1)
        )
        
        # Create active borrow on the same book
        borrow = Borrow.objects.create(
            user=self.admin_user,
            book=self.book_out_of_stock,
            status=Borrow.StatusChoices.BORROWED,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        
        # Log in as admin and return book
        self.client.login(username="admin_user", password="password123")
        return_url = reverse("borrowing:return_book", kwargs={"pk": borrow.pk})
        
        # Clear outbox
        mail.outbox = []
        
        response = self.client.post(return_url)
        self.assertRedirects(response, reverse("borrowing:admin_borrow_list"))
        
        # Verify oldest reservation is now AVAILABLE
        res_oldest.refresh_from_db()
        self.assertEqual(res_oldest.status, Reservation.StatusChoices.AVAILABLE)
        
        # Verify newest reservation is still PENDING
        res_newest.refresh_from_db()
        self.assertEqual(res_newest.status, Reservation.StatusChoices.PENDING)
        
        # Verify notification email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.member_user.email])
        self.assertIn("Reserved Book Available", mail.outbox[0].subject)

    def test_borrowing_available_reserved_book_completes_reservation(self):
        # Setup book and available reservation
        self.book_out_of_stock.available_copies = 1
        self.book_out_of_stock.save()
        
        res = Reservation.objects.create(
            user=self.member_user,
            book=self.book_out_of_stock,
            status=Reservation.StatusChoices.AVAILABLE
        )
        
        self.client.login(username="member_user", password="password123")
        
        # Request borrow book (creates PENDING)
        response = self.client.post(self.borrow_out_url)
        self.assertRedirects(response, self.list_url)
        
        # Verify copies NOT decremented yet
        self.book_out_of_stock.refresh_from_db()
        self.assertEqual(self.book_out_of_stock.available_copies, 1)
        
        borrow = Borrow.objects.get(book=self.book_out_of_stock, user=self.member_user)
        self.assertEqual(borrow.status, Borrow.StatusChoices.PENDING)
        
        # Approve as admin
        self.client.login(username="admin_user", password="password123")
        approve_url = reverse("borrowing:approve_borrow", kwargs={"pk": borrow.pk})
        response = self.client.post(approve_url, {"loan_days": 14})
        self.assertRedirects(response, reverse("borrowing:admin_borrow_requests"))
        
        # Verify copies decremented after approval
        self.book_out_of_stock.refresh_from_db()
        self.assertEqual(self.book_out_of_stock.available_copies, 0)
        
        # Verify reservation status is COMPLETED
        res.refresh_from_db()
        self.assertEqual(res.status, Reservation.StatusChoices.COMPLETED)

    def test_fine_calculation(self):
        # Create a borrow record that is 5 days overdue
        borrow_overdue = Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            borrow_date=timezone.now() - timedelta(days=19),
            due_date=timezone.now() - timedelta(days=5)
        )
        
        # Calculate fine using service (FINE_PER_DAY defaults to 1.00)
        amount = calculate_fine_for_borrow(borrow_overdue)
        self.assertEqual(amount, Decimal("5.00"))

        # Create borrow that is NOT overdue
        borrow_active = Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=5)
        )
        amount_active = calculate_fine_for_borrow(borrow_active)
        self.assertEqual(amount_active, Decimal("0.00"))

    def test_fine_persisted_on_return(self):
        # Create overdue borrow
        borrow = Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.BORROWED,
            borrow_date=timezone.now() - timedelta(days=17),
            due_date=timezone.now() - timedelta(days=3)
        )
        self.book_in_stock.available_copies = 1
        self.book_in_stock.save()

        # Log in as admin and return book
        self.client.login(username="admin_user", password="password123")
        return_url = reverse("borrowing:return_book", kwargs={"pk": borrow.pk})
        
        response = self.client.post(return_url)
        self.assertRedirects(response, reverse("borrowing:admin_borrow_list"))

        # Verify Fine was created with correct amount and is unpaid
        fine = Fine.objects.get(borrow=borrow)
        self.assertEqual(fine.amount, Decimal("3.00"))
        self.assertFalse(fine.is_paid)

    def test_pay_fine_success(self):
        borrow = Borrow.objects.create(
            user=self.member_user,
            book=self.book_in_stock,
            status=Borrow.StatusChoices.RETURNED,
            due_date=timezone.now() - timedelta(days=3),
            return_date=timezone.now()
        )
        fine = Fine.objects.create(
            user=self.member_user,
            borrow=borrow,
            amount=Decimal("3.00"),
            is_paid=False
        )

        self.client.login(username="member_user", password="password123")
        pay_url = reverse("borrowing:pay_fine", kwargs={"pk": fine.pk})
        
        response = self.client.post(pay_url)
        self.assertRedirects(response, self.fines_list_url)

        # Verify fine is paid
        fine.refresh_from_db()
        self.assertTrue(fine.is_paid)
