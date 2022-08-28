import asyncio
import time
import lbry

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

from api.models import Manuscript, Review, Manuscript, ReviewerRecommendation, Researcher
from api.serializers import ManuscriptSerializer, ResearcherSerializer

from papr_server.settings import PAPR_SERVER_NAME, PAPR_SERVER_CHANNEL_NAME


@api_view(["GET"])
def manuscript_list(request):
    if request.method == "GET":
        manuscripts = Manuscript.objects.all().order_by("-id")[:50]
        serializer = ManuscriptSerializer(manuscripts, many=True)
        return Response(serializer.data)


@api_view(["GET"])
def manuscript(request, claim_name):
    if request.method == "GET":
        try:
            manuscript = Manuscript.objects.get(claim_name=claim_name)
        except Manuscript.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ManuscriptSerializer(manuscript)
        return Response(serializer.data)


@api_view(["POST"])
def submit(request):
    if request.method == "POST":
        if "corresponding_author" not in request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if request.data["corresponding_author"] != request.auth["researcher_id"]:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ManuscriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def accept(request):
    if request.method == "POST":
        pass

@api_view(["POST"])
def review(request):
    if request.method == "POST":
        pass

@api_view(["POST"])
def recommend(request):
    if request.method == "POST":
        pass

@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def register(request):
    if "channel_name" not in request.data:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    try:
        existing = Researcher.objects.get(channel_name=request.data['channel_name'])
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
        {
            "name": PAPR_SERVER_NAME,
            "channel_name": PAPR_SERVER_CHANNEL_NAME,
        },
        status=status.HTTP_201_CREATED,
    )

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def info(request):
    return JsonResponse(
        {
            "name": PAPR_SERVER_NAME,
            "channel_name": PAPR_SERVER_CHANNEL_NAME,
        },
        status=status.HTTP_200_OK,
    )

@api_view(["POST"])
def update_contact(request):
    """
        Updates the full name and email of a Researcher account/object.
        Requires the client to be authenticated as this Researcher.
    """
    pass

