from django import forms
from .models import LibrarySettings


class LibrarySettingsForm(forms.ModelForm):
    class Meta:
        model = LibrarySettings
        exclude = ['updated_at', 'updated_by']
        widgets = {
            'site_description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'site_logo': forms.FileInput(attrs={'class': 'form-control'}),
            'favicon': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            css_class = "form-control"
            if field in ['primary_color', 'secondary_color']:
                css_class = "form-control form-control-color"
            if isinstance(self.fields[field], forms.BooleanField):
                css_class = "form-check-input"
            self.fields[field].widget.attrs['class'] = css_class