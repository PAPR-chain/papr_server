from django.urls import path
from api import views

urlpatterns = [
        path('manuscripts/', views.manuscript_list),
        path('manuscripts/<str:claim_name>', views.manuscript),
]
