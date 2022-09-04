import os
import requests

from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from lbry.wallet.manager import WalletManager  # Prevent circular import

from papr.utilities import generate_SECP256k1_keys, SECP_decrypt_text

from api import views
from api.models import *


class AuthenticationTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key, cls.public_key = generate_SECP256k1_keys("test")
        super().setUpClass()

    def setUp(self):
        self.researcher = Researcher.objects.create(
            full_name="Robert Tremblay",
            channel_name="@RTremblay",
            public_key=self.public_key,
        )
        art = SubmittedArticle.objects.create(
                base_claim_name="paper-tremblay",
                corresponding_author=self.researcher,
        )
        m = Manuscript.objects.create(
            claim_name="paper-tremblay",
            title="Theory of Everything",
            authors="Robert Tremblay",
            article=art,
        )

    def tearDown(self):
        pass

    def test_get_manuscript_unauth(self):
        response = self.client.get("/api/article/status/paper-tremblay", format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"], "Authentication credentials were not provided."
        )

    def test_get_token(self):
        response = self.client.get("/api/token/@RTremblay", format="json")
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
        self.assertIn("pub_key", response.json())
        self.assertEqual(response.status_code, 200)

    def test_use_token_get(self):
        response = self.client.get("/api/token/@RTremblay", format="json")

        token_access = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["access"]
        )
        token_refresh = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["refresh"]
        )

        response = self.client.get(
            "/api/article/status/paper-tremblay",
            format="json",
            HTTP_AUTHORIZATION="Bearer " + token_access,
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertIn("base_claim_name", data)
        self.assertEqual(data["base_claim_name"], "paper-tremblay")

        self.assertIn("corresponding_author", data)
        self.assertEqual(data["corresponding_author"], "@RTremblay")

    def test_use_token_post(self):
        response = self.client.get("/api/token/@RTremblay", format="json")

        token_access = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["access"]
        )
        token_refresh = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["refresh"]
        )

        data = {
            "title": "My paper",
            "article": "my-paper",
            "authors": "Robert Tremblay",
            "claim_name": "my-paper_preprint",
            "revision": "0",
            "corresponding_author": "@RTremblay",
        }
        self.assertEqual(Manuscript.objects.count(), 1)

        # The Daemon is required for this action, but is not running
        with self.assertRaises(requests.exceptions.ConnectionError):
            response = self.client.post(
                "/api/article/submit",
                data=data,
                format="json",
                HTTP_AUTHORIZATION="Bearer " + token_access,
            )

    def test_use_token_post_channel_mismatch(self):
        private_key, public_key = generate_SECP256k1_keys("password123")
        Researcher.objects.create(
            full_name="Steve Goder", channel_name="@SGoder", public_key=public_key
        )

        response = self.client.get("/api/token/@RTremblay", format="json")

        token_access = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["access"]
        )
        token_refresh = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["refresh"]
        )

        data = {
            "title": "My paper",
            "claim_name": "my-paper",
            "author_list": "Robert Tremblay",
            "corresponding_author": "@SGoder",
        }
        self.assertEqual(Manuscript.objects.count(), 1)
        response = self.client.post(
            "/api/article/submit",
            data=data,
            format="json",
            HTTP_AUTHORIZATION="Bearer " + token_access,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Manuscript.objects.count(), 1)

    def test_use_token_post_channel_mismatch_does_not_exist(self):
        response = self.client.get("/api/token/@RTremblay", format="json")

        token_access = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["access"]
        )
        token_refresh = SECP_decrypt_text(
            self.private_key, response.json()["pub_key"], response.json()["refresh"]
        )

        data = {
            "title": "My paper",
            "claim_name": "my-paper",
            "author_list": "Robert Tremblay",
            "corresponding_author": "@SGoder",
        }
        self.assertEqual(Manuscript.objects.count(), 1)
        response = self.client.post(
            "/api/article/submit",
            data=data,
            format="json",
            HTTP_AUTHORIZATION="Bearer " + token_access,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Manuscript.objects.count(), 1)

    def test_decrypt_wrong_key(self):
        response = self.client.get("/api/token/@RTremblay", format="json")

        private_key, public_key = generate_SECP256k1_keys("snooper")

        with self.assertRaises(Exception):
            token_access = SECP_decrypt_text(
                private_key, response.json()["pub_key"], response.json()["access"]
            )
        with self.assertRaises(Exception):
            token_refresh = SECP_decrypt_text(
                private_key, response.json()["pub_key"], response.json()["refresh"]
            )

    # refresh token


