from django.db import models
from django.core.validators import EmailValidator
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .managers import ResearcherManager

class Researcher(AbstractBaseUser, PermissionsMixin):
    channel_name = models.CharField(max_length=255, unique=True)

    joined = models.DateTimeField(auto_now_add=True)
    full_name = models.CharField(max_length=255, default="", blank=True)
    public_key = models.CharField(max_length=316, null=True)
    email = models.EmailField(null=True, validators=[EmailValidator])

    USERNAME_FIELD = 'channel_name'
    REQUIRED_FIELDS = []

    objects = ResearcherManager()

    # Fields of research?
    # Number of manuscripts/reviews?
    # URL to proof of channel

    def __str__(self):
        return self.channel_name

class Review(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    text = models.TextField(max_length=4194304) # 4 MB
    reviewer = models.ForeignKey(Researcher, on_delete=models.SET_NULL, null=True)
    manuscript = models.ForeignKey('Manuscript', on_delete=models.SET_NULL, null=True)
    rating = models.PositiveSmallIntegerField(default=0)

class Manuscript(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    claim_name = models.CharField(max_length=255, unique=True)
    #claim_id = models.CharField(max_length=40, unique=True)
    title = models.TextField(max_length=1024)
    author_list = models.TextField(max_length=1024)
    corresponding_author = models.ForeignKey(Researcher, on_delete=models.SET_NULL, null=True)

    public_key = models.CharField(max_length=1024, null=True)
    review_password = models.CharField(max_length=1024, null=True)

    encrypted = models.BooleanField(default=False)
    encryption_password = models.CharField(max_length=1024, null=True)

    status = models.PositiveSmallIntegerField(default=0)

    """
    Statuses:
        0: Pending review
        1: First reviews sent to authors, pending action
        2: First revision submitted by the authors, pending second round of reviews
        ...
        99: Abandonned
        100: Officially published
    """


class ReviewerRecommendation(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    reviewer = models.ForeignKey(Researcher, related_name="is_recommended", on_delete=models.SET_NULL, null=True)
    voucher = models.ForeignKey(Researcher, related_name="has_recommended", on_delete=models.SET_NULL, null=True)
    manuscript = models.ForeignKey(Manuscript, related_name="recommendations", on_delete=models.SET_NULL, null=True)

