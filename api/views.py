import asyncio
import time
import lbry
import logging

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

from papr.cli import call
from papr.utilities import DualLogger

from api.models import (
    Review,
    Manuscript,
    ReviewerRecommendation,
    Researcher,
    SubmittedArticle,
)
from api.serializers import (
    ManuscriptSerializer,
    ResearcherSerializer,
    SubmittedArticleSerializer,
    ReviewSerializer,
    ReviewerRecommendationSerializer,
)

from papr_server.settings import PAPR_SERVER_NAME, PAPR_SERVER_CHANNEL_NAME

logger = DualLogger(logging.getLogger(__name__))

SERVER_DESC = {
    "name": PAPR_SERVER_NAME,
    "channel_name": PAPR_SERVER_CHANNEL_NAME,
    # url?
}


@api_view(["GET"])
def article_status(request, base_claim_name):
    try:
        article = SubmittedArticle.objects.get(base_claim_name=base_claim_name)
    except Manuscript.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if article.corresponding_author.channel_name != request.auth["researcher_id"]:
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = SubmittedArticleSerializer(article)
    return Response(serializer.data)


@api_view(["POST"])
def submit(request):
    """
    Submit a manuscript for peer-review mediated by this server.
    The manuscript is already published on the LBRY blockchain.
    It can be a preprint or a new revision of an article under review.
    """
    if request.method == "POST":
        if "corresponding_author" not in request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if request.data["corresponding_author"] != request.auth["researcher_id"]:
            return Response(
                logger.error(
                    "You are not authenticated as the corresponding author of the publication"
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        if "revision" not in request.data:
            return Response(
                logger.error("You must submit a revision number"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_claim_name = request.data["article"]
        request.data["base_claim_name"] = base_claim_name
        try:
            article = SubmittedArticle.objects.get(base_claim_name=base_claim_name)
        except SubmittedArticle.DoesNotExist:
            art_ser = SubmittedArticleSerializer(data=request.data)
            if not art_ser.is_valid():
                return Response(art_ser.errors, status=status.HTTP_400_BAD_REQUEST)
            art_ser.save()
        else:
            if request.data["revision"] == 0 and article.status != 0:
                return Response(
                    logger.error(
                        "An article with the given base claim name already exists. Submit a revision instead."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

        man_ser = ManuscriptSerializer(data=request.data)
        if not man_ser.is_valid():
            return Response(man_ser.errors, status=status.HTTP_400_BAD_REQUEST)

        res = call("resolve", urls=request.data["claim_name"]).json()
        if (
            request.data["claim_name"] not in res["result"]
            or "error" in res["result"][request.data["claim_name"]]
        ):
            return Response(
                logger.error("Publication not found on the blockchain"),
                status=status.HTTP_404_NOT_FOUND,
            )

        pub_data = res["result"][request.data["claim_name"]]

        if (
            "is_channel_signature_valid" not in pub_data
            or not pub_data["is_channel_signature_valid"]
            or pub_data["signing_channel"]["name"] != request.auth["researcher_id"]
        ):
            return Response(
                logger.error(
                    "The submitted manuscript is not signed by the authenticated channel"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pub_data["value"]["title"] != request.data["title"]:
            return Response(
                logger.error(
                    "The submitted title does not match the title of the publication"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pub_data["value"]["author"] != request.data["authors"]:
            return Response(
                logger.error(
                    "The submitted author list does not match the author list of the publication"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        man_ser.save()
        return Response(man_ser.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def article_accept(request):
    # TODO
    pass


@api_view(["POST"])
def reviewrequest_decline(request):
    return _reviewrequest_modify(request, accept=false)


@api_view(["POST"])
def reviewrequest_accept(request):
    return _reviewrequest_modify(request, accept=True)


def _reviewrequest_modify(request, accept=True):
    if "base_claim_name" not in request.data:
        return Response(
            logger.error("An article base claim name must be specified"),
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        article = SubmittedArticle.objects.get(
            base_claim_name=request.data["base_claim_name"]
        )
    except SubmittedArticle.DoesNotExist:
        return Response(
            logger.error(
                "No article with the base claim name {request.data['base_claim_name']}"
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    pending_requests = ReviewRequest.objects.filter(article=article, status=1)
    if pending_requests.count() == 0:
        specific_request = ReviewRequest.objects.filter(
            article=article, reviewer__channel_name=request.auth["researcher_id"]
        )
        if specific_request.count() == 0:
            return Response(
                logger.error(
                    "No review was requested from channel {request.auth['researcher_id']}"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            # TODO: more details
            return Response(
                logger.error("You have already replied to the review request"),
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        relevant_requests = pending_requests.filter(
            reviewer__channel_name=request.auth["researcher_id"]
        )
        if relevant_requests.count() == 0:
            return Response(
                logger.error(
                    "No review was requested from channel {request.auth['researcher_id']}"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif relevant_requests.count() == 1:
            req = relevant_requests.first()
            if accept:
                req.status = 3
                req.save()
                return Response(
                    logger.info(
                        "The review request has been marked as accepted, thank you!"
                    ),
                    status=status.HTTP_200_OK,
                )
            else:
                req.status = 2
                req.save()
                return Response(
                    logger.info("The review request has been marked as declined."),
                    status=status.HTTP_200_OK,
                )
        else:
            raise Exception(
                f"Multiple pending requests for {request.auth['researcher_id']} and article {article.base_claim_name}, this should not happen"
            )


@api_view(["POST"])
def review(request):
    # Prevent the user from getting information about reviewers
    if "reviewer" in request.data:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    serializer = ReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    man = Manuscript.objects.get(claim_name=request.data["manuscript"])
    pending_reviews = man.article.reviewers_contacted.filter(
        status=3, reviewer__channel_name=request.auth["researcher_id"]
    )
    if pending_reviews.count() == 0:
        return Response(
            logger.error(
                f"No review was requested from channel {request.auth['researcher_id']} for article {man.article}"
            ),
            status=status.HTTP_404_NOT_FOUND,
        )
    elif pending_reviews.count() == 1:
        req = pending_reviews.first()
        req.status = 4
        req.save()
    else:
        raise Exception(
            f"Multiple pending requests for {request.auth['researcher_id']} and article {article.base_claim_name}, this should not happen"
        )

    serializer.save(reviewer=reviewer, request=req)

    return Response(
        logger.info(
            f"Your review of {man.article.base_claim_name} (man.claim_name) has been received, thank you!"
        ),
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def recommend(request):

    # TODO: Confirm the reviewer's identity using the submitted name
    request.data["voucher"] = request.auth["researcher_id"]

    serializer = ReviewerRecommendationSerializer(data=request.data)
    if not serializer.is_valid():
        # TODO: handle reviewers which are not registered to that review server
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()

    return Response(
        logger.info(
            f"Your review recommendation for {request.data['article']} has been received, thank you!"
        ),
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def register(request):
    if "channel_name" not in request.data:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    try:
        existing = Researcher.objects.get(channel_name=request.data["channel_name"])
    except Researcher.DoesNotExist:
        pass
    else:
        return Response(status=status.HTTP_403_FORBIDDEN)

    serializer = ResearcherSerializer(data=request.data)

    channel_name = request.data["channel_name"]

    if not serializer.is_valid():
        return Response(status=status.HTTP_404_NOT_FOUND)

    ret = call("macro_get_public_key", channel_name=channel_name)
    if "error" in ret:
        return Response(status=status.HTTP_404_NOT_FOUND)

    data = ret.json()
    if "info" in data["result"]:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer.save(public_key=data["result"]["public_key"])
    # return server info
    ## Description
    ## Public key

    return JsonResponse(
        SERVER_DESC,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def info(request):
    return JsonResponse(
        SERVER_DESC,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def update_contact(request):
    """
    Updates the full name and email of a Researcher account/object.
    Requires the client to be authenticated as this Researcher.
    """
    # TODO
    pass
