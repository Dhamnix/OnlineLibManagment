from django.utils import timezone
from .models import Notification

def create_notification(user, notification_type, title, message, link=None):
    """Create a new notification for a user."""
    notification = Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        link=link,
        created_at=timezone.now()
    )
    return notification

def notify_borrow(borrow):
    """Send notification when a book is borrowed."""
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.BORROW,
        title=f"📚 Book Borrowed: {borrow.book.title}",
        message=(
            f"You have successfully borrowed '{borrow.book.title}' by {borrow.book.author}.\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return the book on or before the due date."
        ),
        link="/borrowing/"
    )

def notify_return(borrow):
    """Send notification when a book is returned."""
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.RETURN,
        title=f"✅ Book Returned: {borrow.book.title}",
        message=(
            f"You have successfully returned '{borrow.book.title}' by {borrow.book.author}.\n"
            f"📅 Return Date: {borrow.return_date.strftime('%Y-%m-%d')}\n"
            f"Thank you for returning the book!"
        ),
        link="/borrowing/history/"
    )

def notify_reservation(reservation):
    """Send notification when a reserved book becomes available."""
    create_notification(
        user=reservation.user,
        notification_type=Notification.Type.RESERVATION,
        title=f"🔔 Reserved Book Available: {reservation.book.title}",
        message=(
            f"The book '{reservation.book.title}' by {reservation.book.author} you reserved is NOW AVAILABLE!\n"
            f"Please visit the library and borrow it."
        ),
        link=f"/books/{reservation.book.pk}/"
    )

def notify_reservation_created(reservation):
    """Send notification when a book is reserved."""
    create_notification(
        user=reservation.user,
        notification_type=Notification.Type.RESERVATION,
        title=f"📌 Book Reserved: {reservation.book.title}",
        message=(
            f"You have successfully reserved '{reservation.book.title}' by {reservation.book.author}.\n"
            f"📅 Reservation Date: {reservation.reservation_date.strftime('%Y-%m-%d')}\n"
            f"We will notify you when the book becomes available."
        ),
        link="/borrowing/reservations/"
    )

def notify_fine(fine):
    """Send notification when a fine is created."""
    create_notification(
        user=fine.user,
        notification_type=Notification.Type.FINE,
        title=f"💰 Fine Incurred: ${fine.amount}",
        message=(
            f"You have incurred a fine of ${fine.amount} for late return of '{fine.borrow.book.title}'.\n"
            f"📅 Due Date: {fine.borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please pay the fine as soon as possible."
        ),
        link="/borrowing/fines/"
    )

def notify_fine_paid(fine):
    """Send notification when a fine is paid."""
    create_notification(
        user=fine.user,
        notification_type=Notification.Type.FINE,
        title=f"✅ Fine Paid: ${fine.amount}",
        message=(
            f"You have successfully paid the fine of ${fine.amount} for '{fine.borrow.book.title}'.\n"
            f"Thank you for clearing your fines!"
        ),
        link="/borrowing/fines/"
    )

def notify_reminder(borrow, days_left):
    """Send reminder notification for approaching due date."""
    if days_left == 0:
        title = f"⚠️ BOOK DUE TODAY: {borrow.book.title}"
        message = (
            f"WARNING: '{borrow.book.title}' is due TODAY!\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return it TODAY to avoid fines!"
        )
    elif days_left == 1:
        title = f"⏰ Reminder: {borrow.book.title} Due Tomorrow"
        message = (
            f"REMINDER: '{borrow.book.title}' is due TOMORROW!\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return it tomorrow."
        )
    else:
        title = f"📖 Reminder: {borrow.book.title} Due in {days_left} Days"
        message = (
            f"REMINDER: '{borrow.book.title}' is due in {days_left} days.\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return it on time."
        )
    
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.REMINDER,
        title=title,
        message=message,
        link="/borrowing/"
    )

def notify_overdue(borrow):
    """Send notification for overdue books."""
    days_overdue = (timezone.now() - borrow.due_date).days
    
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.REMINDER,
        title=f"🚨 OVERDUE: {borrow.book.title}",
        message=(
            f"WARNING: '{borrow.book.title}' is OVERDUE by {days_overdue} day(s)!\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return it IMMEDIATELY!"
        ),
        link="/borrowing/fines/"
    )

def notify_welcome(user):
    """Send welcome notification when a user registers."""
    create_notification(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title="🎉 Welcome to OnlineLib!",
        message=(
            f"Hello {user.username}! Welcome to OnlineLib Library.\n\n"
            f"Here's what you can do:\n"
            f"📚 Browse and search for books\n"
            f"📖 Borrow books and track due dates\n"
            f"🔔 Reserve unavailable books\n"
            f"⭐ Rate and review books you've read\n"
            f"💳 Pay fines online\n\n"
            f"Start your reading journey today!"
        ),
        link="/books/"
    )

def notify_profile_updated(user):
    """Send notification when profile is updated."""
    create_notification(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title="✅ Profile Updated",
        message="Your profile information has been updated successfully.",
        link="/accounts/profile/"
    )

def notify_password_changed(user):
    """Send notification when password is changed."""
    create_notification(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title="🔐 Password Changed",
        message="Your password has been changed successfully.",
        link="/accounts/profile/"
    )

def notify_review_added(user, book, rating):
    """Send notification when a review is added."""
    create_notification(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title=f"⭐ Review Added: {book.title}",
        message=(
            f"You have successfully added a review for '{book.title}'.\n"
            f"⭐ Rating: {rating}/5\n"
            f"Thank you for sharing your thoughts!"
        ),
        link=f"/books/{book.pk}/"
    )

def notify_review_updated(user, book, rating):
    """Send notification when a review is updated."""
    create_notification(
        user=user,
        notification_type=Notification.Type.SYSTEM,
        title=f"🔄 Review Updated: {book.title}",
        message=(
            f"You have updated your review for '{book.title}'.\n"
            f"⭐ New Rating: {rating}/5"
        ),
        link=f"/books/{book.pk}/"
    )

def notify_reservation_cancelled(reservation):
    """Send notification when a reservation is cancelled."""
    create_notification(
        user=reservation.user,
        notification_type=Notification.Type.RESERVATION,
        title=f"❌ Reservation Cancelled: {reservation.book.title}",
        message=(
            f"You have cancelled your reservation for '{reservation.book.title}'.\n"
            f"You can reserve it again later if you change your mind."
        ),
        link="/borrowing/reservations/"
    )


def notify_borrow_request(borrow):
    """Send notification to admins when a user submits a borrow request."""
    from django.conf import settings
    User = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
    admins = User.objects.filter(role='ADMIN')
    
    for admin_user in admins:
        create_notification(
            user=admin_user,
            notification_type=Notification.Type.BORROW,
            title=f"📋 New Borrow Request: {borrow.book.title}",
            message=(
                f"User '{borrow.user.username}' has requested to borrow '{borrow.book.title}' "
                f"by {borrow.book.author}.\n"
                f"📅 Request Date: {borrow.request_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"Please review and approve or reject this request."
            ),
            link="/borrowing/admin/requests/"
        )


def notify_borrow_approved(borrow, loan_days):
    """Send notification to user when their borrow request is approved."""
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.BORROW,
        title=f"✅ Borrow Request Approved: {borrow.book.title}",
        message=(
            f"Your borrow request for '{borrow.book.title}' has been APPROVED!\n"
            f"📅 Borrow Date: {borrow.borrow_date.strftime('%Y-%m-%d')}\n"
            f"📅 Due Date: {borrow.due_date.strftime('%Y-%m-%d')}\n"
            f"📆 Loan Period: {loan_days} days\n"
            f"Please return the book on or before the due date to avoid fines."
        ),
        link="/borrowing/"
    )


def notify_borrow_rejected(borrow):
    """Send notification to user when their borrow request is rejected."""
    create_notification(
        user=borrow.user,
        notification_type=Notification.Type.BORROW,
        title=f"❌ Borrow Request Rejected: {borrow.book.title}",
        message=(
            f"Your borrow request for '{borrow.book.title}' has been rejected.\n"
            f"📝 Reason: {borrow.rejected_reason}\n"
            f"You can contact the library for more information."
        ),
        link="/borrowing/"
    )