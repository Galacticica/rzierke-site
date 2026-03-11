from django import forms

from .models import AIModel, AIQuirk


class AIModelForm(forms.ModelForm):
    class Meta:
        model = AIModel
        fields = ["name", "description", "quirk"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "Model name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full",
                    "rows": 3,
                    "placeholder": "Model description",
                }
            ),
            "quirk": forms.SelectMultiple(
                attrs={
                    "class": "select select-bordered w-full min-h-32",
                }
            ),
        }


class AIQuirkForm(forms.ModelForm):
    class Meta:
        model = AIQuirk
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "Quirk name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full",
                    "rows": 3,
                    "placeholder": "Quirk description",
                }
            ),
        }
