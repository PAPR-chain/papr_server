from rest_framework.serializers import ModelSerializer, SlugRelatedField

from .models import Manuscript, Researcher, Review, ReviewerRecommendation

class ManuscriptSerializer(ModelSerializer):
    corresponding_author = SlugRelatedField(many=False, slug_field='channel_name', queryset=Researcher.objects.all())

    class Meta:
        model = Manuscript
        fields = ['title', 'claim_name', 'author_list', 'status', 'corresponding_author']


class ResearcherSerializer(ModelSerializer):
    class Meta:
        model = Researcher
        fields = ['full_name', 'channel_name', 'email']

class ReviewSerializer(ModelSerializer):
    class Meta:
        model = Review
        fields = ['text']

class ReviewerRecommendationSerializer(ModelSerializer):
    class Meta:
        model = ReviewerRecommendation
        fields = ['manuscript']
