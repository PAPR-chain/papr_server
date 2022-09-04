from django.urls import include, path
from django.contrib.auth.models import User

from rest_framework import routers, serializers, viewsets
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from lbry.wallet.manager import WalletManager  # Prevent circular import

from papr_server import views

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("api/", include("api.urls")),
    # path("api/token/", TokenObtainPairView.as_view()),
    path("api/token/<str:channel_name>", views.get_token),
    path("api/token/refresh", TokenRefreshView.as_view()),  # TODO: use
    path("api-auth/", include("rest_framework.urls")),  # TODO: use
]
