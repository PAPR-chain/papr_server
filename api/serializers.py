from rest_framework.serializers import (
    ModelSerializer,
    SlugRelatedField,
    SerializerMethodField,
    ValidationError,
    RelatedField,
)

from api.models import (
    Manuscript,
    SubmittedArticle,
    Researcher,
    Review,
    ReviewerRecommendation,
)


class ManuscriptSerializer(ModelSerializer):
    article = SlugRelatedField(
        many=False,
        slug_field="base_claim_name",
        queryset=SubmittedArticle.objects.all(),
    )

    class Meta:
        model = Manuscript
        fields = ["title", "claim_name", "authors", "abstract", "article"]


class SubmittedArticleSerializer(ModelSerializer):
    corresponding_author = SlugRelatedField(
        many=False, slug_field="channel_name", queryset=Researcher.objects.all()
    )

    class Meta:
        model = SubmittedArticle
        fields = ["base_claim_name", "corresponding_author", "revision"]
        read_only_fields = ["reviewed", "status"]


class ResearcherSerializer(ModelSerializer):
    class Meta:
        model = Researcher
        fields = ["full_name", "channel_name", "email"]


class ReviewSerializer(ModelSerializer):
    class Meta:
        model = Review
        fields = ["text"]


class ReviewerRecommendationSerializer(ModelSerializer):
    class Meta:
        model = ReviewerRecommendation
        fields = ["manuscript"]
