from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, f"{i} Star{'s' if i != 1 else ''}") for i in range(1, 6)],
        widget=forms.RadioSelect,
        label="Rating"
    )
    
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Share your thoughts about this book...",
                    "class": "form-control"
                }
            ),
        }
        labels = {
            "comment": "Your Review (Optional)",
        }
