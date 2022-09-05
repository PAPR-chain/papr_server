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
    manuscript = SlugRelatedField(
        many=False,
        slug_field="claim_name",
        queryset=Manuscript.objects.all(),
    )
    reviewer = SlugRelatedField(
        many=False,
        slug_field="channel_name",
        queryset=Researcher.objects.all(),
    )

    # Verify signature

    class Meta:
        model = Review
        fields = ["text", "rating", "manuscript", "reviewer", "signature", "signing_ts"]


class ReviewerRecommendationSerializer(ModelSerializer):
    reviewer = SlugRelatedField(
        many=False,
        slug_field="channel_name",
        queryset=Researcher.objects.all(),
    )
    voucher = SlugRelatedField(
        many=False,
        slug_field="channel_name",
        queryset=Researcher.objects.all(),
    )

    article = SlugRelatedField(
        many=False,
        slug_field="base_claim_name",
        queryset=SubmittedArticle.objects.all(),
    )

    def validate(self, data):
        if data["voucher"] == data["reviewer"]:
            raise ValidationError("You cannot recommend yourself")
        if (
            ReviewerRecommendation.objects.filter(
                article=data["article"],
                voucher=data["voucher"],
                reviewer=data["reviewer"],
            ).count()
            != 0
        ):
            raise ValidationError(
                "You have already made this exact same recommendation"
            )
        return data

    class Meta:
        model = ReviewerRecommendation
        fields = ["article", "reviewer", "voucher"]
