
from django.urls import path
from . import views

app_name = "worksphere_team"

urlpatterns = [
    path("", views.team_list, name="team_list"),
]
