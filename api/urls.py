from django.urls import path
from api import views

urlpatterns = [
        #path('manuscripts/', views.manuscript_list),
        path('status/<str:base_claim_name>', views.article_status),
        path('register/', views.register),
        path('submit/', views.submit),
        path('accept/', views.accept),
        path('review/', views.review),
        path('recommend/', views.recommend),
        path('update_contact/', views.update_contact),
        path('info/', views.info),
]
