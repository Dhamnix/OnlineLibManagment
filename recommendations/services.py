from typing import List
from django.db.models import Count, Avg

from books.models import Book
from borrowing.models import Borrow


def get_user_top_genres(user, top_n: int = 3) -> List[str]:
    """Return user's top N genres based on their borrow history."""
    borrowed_book_ids = Borrow.objects.filter(user=user).values_list("book_id", flat=True)
    if not borrowed_book_ids:
        return []

    genres = (
        Book.objects.filter(pk__in=borrowed_book_ids)
        .values("genre")
        .annotate(count=Count("id"))
        .order_by("-count")[:top_n]
    )
    return [g["genre"] for g in genres]


def recommend_for_user(user, limit: int = 5) -> List[Book]:
    """Recommend books for a user based on borrow history, genres and ratings.

    Strategy:
    1. Find top genres from user's borrow history and recommend popular/high-rated
       books in those genres that the user hasn't already borrowed.
    2. If not enough results, add books borrowed by other users who borrowed
       the same books (co-borrowed).
    """
    # Books the user already interacted with
    user_borrowed_ids = list(Borrow.objects.filter(user=user).values_list("book_id", flat=True))

    # Primary: recommend by top genres
    top_genres = get_user_top_genres(user, top_n=3)

    qs = (
        Book.objects.filter(available_copies__gt=0)
        .exclude(pk__in=user_borrowed_ids)
        .annotate(borrow_count=Count("borrowings"), avg_rating=Avg("reviews__rating"))
    )

    recommendations = []

    if top_genres:
        genre_qs = qs.filter(genre__in=top_genres).order_by("-borrow_count", "-avg_rating", "title")[:limit]
        recommendations = list(genre_qs)

    # If we still need more, add co-borrowed books
    if len(recommendations) < limit and user_borrowed_ids:
        # Users who borrowed same books
        other_user_ids = (
            Borrow.objects.filter(book_id__in=user_borrowed_ids)
            .exclude(user=user)
            .values_list("user_id", flat=True)
            .distinct()
        )
        co_borrowed_qs = (
            qs.filter(borrowings__user_id__in=other_user_ids)
            .exclude(pk__in=user_borrowed_ids)
            .annotate(shared_count=Count("borrowings"))
            .order_by("-shared_count", "-borrow_count")
            .distinct()
        )

        for b in co_borrowed_qs:
            if b in recommendations:
                continue
            recommendations.append(b)
            if len(recommendations) >= limit:
                break

    # Final fallback: popular books overall
    if len(recommendations) < limit:
        popular = qs.order_by("-borrow_count", "-avg_rating", "title")[: limit - len(recommendations)]
        for b in popular:
            if b in recommendations:
                continue
            recommendations.append(b)

    return recommendations[:limit]


def similar_books(book: Book, limit: int = 5) -> List[Book]:
    """Find similar books by genre and ratings using ORM only."""
    if not book:
        return []

    qs = (
        Book.objects.filter(genre=book.genre)
        .exclude(pk=book.pk)
        .annotate(borrow_count=Count("borrowings"), avg_rating=Avg("reviews__rating"))
        .order_by("-avg_rating", "-borrow_count", "title")[:limit]
    )
    return list(qs)
