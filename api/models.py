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

class SubmittedArticle(models.Model):
    base_claim_name = models.CharField(max_length=255, unique=True)
    corresponding_author = models.ForeignKey(Researcher, on_delete=models.SET_NULL, null=True)

    encryption_passphrase = models.CharField(max_length=1024)
    review_passphrase = models.CharField(max_length=1024)

    reviewed = models.BooleanField(default=False)
    revision = models.PositiveSmallIntegerField(default=0)

    status = models.PositiveSmallIntegerField(default=0)

    """
    Statuses:
        0: Incomplete entry
        1: Pending review
        2: First reviews sent to authors, pending action
        3: First revision submitted by the authors, pending second round of reviews
        ...
        99: Abandonned
        100: Officially published
    """

    @property
    def latest_manuscript(self):
        return self.manuscript_set.latest('submitted')

    @property
    def title(self):
        return self.latest_manuscript.title

    @property
    def abstract(self):
        return self.latest_manuscript.abstract

    @property
    def authors(self):
        return self.latest_manuscript.authors

    @property
    def tags(self):
        return self.latest_manuscript.tags

class Manuscript(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    claim_name = models.CharField(max_length=255, unique=True)
    #claim_id = models.CharField(max_length=40, unique=True)
    title = models.TextField(max_length=1024)
    authors = models.TextField(max_length=1024)
    tags = models.TextField(max_length=1024, default="")
    abstract = models.TextField(default="")

    public_key = models.CharField(max_length=1024, null=True)
    review_password = models.CharField(max_length=1024, null=True)

    encrypted = models.BooleanField(default=False)
    encryption_password = models.CharField(max_length=1024, null=True)

    article = models.ForeignKey(SubmittedArticle, related_name="version", on_delete=models.SET_NULL, null=True)



class ReviewerRecommendation(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    reviewer = models.ForeignKey(Researcher, related_name="is_recommended", on_delete=models.SET_NULL, null=True)
    voucher = models.ForeignKey(Researcher, related_name="has_recommended", on_delete=models.SET_NULL, null=True)
    manuscript = models.ForeignKey(Manuscript, related_name="recommendations", on_delete=models.SET_NULL, null=True)

