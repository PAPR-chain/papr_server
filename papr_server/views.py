import asyncio
import unittest # Sets the IS_TEST variable to True

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Manuscript, Review, Manuscript, ReviewerRecommendation
from api.serializers import ManuscriptSerializer
from api.models import Researcher

from papr.utilities import generate_SECP256k1_keys, SECP_encrypt_text, SECP_decrypt_text


@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_token(request, channel_name):
    """
        Generates a token for the requested channel and encrypts it using a ECDH shared secret derived from the (alledged) recipient's public key (retrieved from the LBRY network).
        As such, only the true owner of the channel can decrypt and use the token.
    """
    # Clean token name?
    try:
        target = Researcher.objects.get(channel_name=channel_name)
    except Researcher.DoesNotExist:
        # Could also return gibberish to provide no information about the existing objects
        return Response(status=status.HTTP_404_NOT_FOUND)

    if not target.public_key:
        return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

    token = RefreshToken.for_user(target)

    priv_key, pub_key = generate_SECP256k1_keys(None) # Random key

    refresh = SECP_encrypt_text(priv_key, target.public_key, str(token))
    access = SECP_encrypt_text(priv_key, target.public_key, str(token.access_token))

    return JsonResponse({
        'refresh': refresh,
        'access': access,
        'pub_key': pub_key,
        })

