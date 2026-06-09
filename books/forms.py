from django import forms

from .models import Book


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = (
            "title",
            "author",
            "genre",
            "description",
            "publish_year",
            "isbn",
            "total_copies",
            "available_copies",
            "cover_image",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            css_class = "form-control"
            if field_name == "cover_image":
                css_class = "form-control"
            field.widget.attrs["class"] = css_class

        self.fields["available_copies"].required = False
        self.fields["available_copies"].help_text = (
            "Leave blank to match total copies when saving."
        )

    def clean_available_copies(self):
        available_copies = self.cleaned_data.get("available_copies")
        total_copies = self.cleaned_data.get("total_copies")

        if available_copies is None and total_copies is not None:
            return total_copies

        return available_copies
