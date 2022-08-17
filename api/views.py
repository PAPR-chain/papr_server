from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import Manuscript, Review, Manuscript, ReviewerRecommendation
from api.serializers import ManuscriptSerializer

@api_view(['GET'])
def manuscript_list(request):
    if request.method == 'GET':
        manuscripts = Manuscript.objects.all().order_by('-id')[:50]
        serializer = ManuscriptSerializer(manuscripts, many=True)
        return Response(serializer.data)

@api_view(['GET', 'POST'])
def manuscript(request, claim_name):
    if request.method == 'GET':
        try:
            manuscript = Manuscript.objects.get(claim_name=claim_name)
        except Manuscript.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ManuscriptSerializer(manuscript)
        return Response(serializer.data)
    elif request.method == 'POST':
        if "corresponding_author" not in request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if request.data["corresponding_author"] != request.auth["researcher_id"]:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = ManuscriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
