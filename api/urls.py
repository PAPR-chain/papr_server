from django.urls import path
from api import views

urlpatterns = [
    # path('manuscripts/', views.manuscript_list),
    path("article/status/<str:base_claim_name>", views.article_status),
    path("article/submit", views.submit),
    path("article/accept", views.article_accept),
    path("article/review", views.review),
    path("channel/register", views.register),
    path("channel/update_contact", views.update_contact),
    path("info/", views.info),
    path("review/accept", views.reviewrequest_accept),
    path("review/decline", views.reviewrequest_decline),
    path("review/recommend", views.recommend),
]
