from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver

from .models import CustomUser


def create_groups_and_permissions():
    try:
        # Get or create content types for roles mapping
        books_ct, _ = ContentType.objects.get_or_create(app_label="books", model="book")
        borrowing_ct, _ = ContentType.objects.get_or_create(app_label="borrowing", model="borrowing")
        reviews_ct, _ = ContentType.objects.get_or_create(app_label="reviews", model="reviews")

        # Define permissions
        permissions_data = {
            # Books permissions
            "add_book": (books_ct, "Can add book"),
            "change_book": (books_ct, "Can change book"),
            "delete_book": (books_ct, "Can delete book"),
            "view_book": (books_ct, "Can view book"),
            # Borrowings permissions
            "manage_borrowings": (borrowing_ct, "Can manage borrowings"),
            "borrow_books": (borrowing_ct, "Can borrow books"),
            # Reviews permissions
            "review_books": (reviews_ct, "Can review books"),
        }

        permissions = {}
        for codename, (ct, name) in permissions_data.items():
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={"name": name}
            )
            permissions[codename] = perm

        # Create Librarian Group
        librarian_group, _ = Group.objects.get_or_create(name="Librarian")
        librarian_perms = [
            permissions["add_book"],
            permissions["change_book"],
            permissions["delete_book"],
            permissions["manage_borrowings"],
        ]
        librarian_group.permissions.set(librarian_perms)

        # Create Member Group
        member_group, _ = Group.objects.get_or_create(name="Member")
        member_perms = [
            permissions["view_book"],
            permissions["borrow_books"],
            permissions["review_books"],
        ]
        member_group.permissions.set(member_perms)

        return librarian_group, member_group
    except Exception:
        # Prevent database lock or failure during early migrations when tables are missing
        return None, None


@receiver(post_migrate)
def setup_groups_on_migrate(sender, **kwargs):
    if sender.name == "accounts":
        create_groups_and_permissions()


@receiver(post_save, sender=CustomUser)
def assign_user_to_group(sender, instance, created, **kwargs):
    librarian_group, member_group = create_groups_and_permissions()

    if librarian_group and member_group:
        # Clean existing groups to assign only the active role
        instance.groups.remove(librarian_group, member_group)
        
        if instance.role == CustomUser.Role.ADMIN:
            instance.groups.add(librarian_group)
        else:
            instance.groups.add(member_group)
