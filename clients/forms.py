
from django import forms
from .models import ProjectRequest, ClientFeedback


class ProjectRequestForm(forms.ModelForm):
    class Meta:
        model = ProjectRequest
        fields = [
            "title",
            "description",
            "budget",
            "deadline",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 5}
            ),
            "deadline": forms.DateInput(
                attrs={"type": "date"}
            ),
        }


class ClientFeedbackForm(forms.ModelForm):
    class Meta:
        model = ClientFeedback
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 4}
            ),
        }


class ReviewRequestForm(forms.ModelForm):
    class Meta:
        model = ProjectRequest
        fields = ["status", "manager_notes"]
        widgets = {
            "manager_notes": forms.Textarea(
                attrs={"rows": 4}
            ),
        }

