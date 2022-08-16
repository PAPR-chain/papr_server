from django.urls import include, path
from django.contrib.auth.models import User

from rest_framework import routers, serializers, viewsets
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
'''
# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'is_staff']

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
'''

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
#router.register(r'users', UserViewSet)

urlpatterns = [
        path('', include(router.urls)),
        path("api/", include("api.urls")),
        path("api/token/", TokenObtainPairView.as_view()),
        path("api/token/refresh", TokenRefreshView.as_view()),
        path('api-auth/', include('rest_framework.urls')),
]
