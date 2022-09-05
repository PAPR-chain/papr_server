import asyncio
import os
import tempfile
import warnings
import logging
import json
import re
import base64
import datetime
from aioresponses import aioresponses
from asgiref.sync import sync_to_async
from zipfile import ZipFile
from sqlalchemy.orm import Session

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from lbry.testcase import IntegrationTestCase, CommandTestCase
from lbry.crypto.hash import sha256
from lbry.crypto.crypt import better_aes_decrypt

from papr.utilities import file_sha256
from papr.models import Article as ClientArticle
from papr.models import Manuscript as ClientManuscript

from api.models import Researcher, Manuscript, SubmittedArticle, ReviewerRecommendation, Review
from api.views import submit, register
from papr_server.testcase import PaprDaemonAPITestCase

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class RegisterTests(PaprDaemonAPITestCase):
    async def test_register(self):
        tx = await self.daemon.jsonrpc_channel_create("@RTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 0)
        response = await sync_to_async(self.client.post)(
            "/api/channel/register", format="json", data={"channel_name": "@RTremblay"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 1)

        chan = await self.daemon.jsonrpc_channel_list()
        pubkey_hex = chan["items"][0].claim.channel.public_key
        pubkey = base64.b64encode(bytes.fromhex(pubkey_hex)).decode()

        saved_key = (
            await sync_to_async(Researcher.objects.get)(channel_name="@RTremblay")
        ).public_key
        self.assertEqual(saved_key, pubkey)

    async def test_register_duplicate(self):
        tx = await self.daemon.jsonrpc_channel_create("@RTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 0)
        researcher = await sync_to_async(Researcher.objects.create)(
            full_name="Robert Tremblay", channel_name="@RTremblay"
        )
        token = RefreshToken.for_user(researcher)
        response = await sync_to_async(self.client.post)(
            "/api/channel/register",
            format="json",
            data={"channel_name": "@RTremblay"},
            headers={"HTTP_AUTHORIZATION": f"Bearer {str(token.access_token)}"},
        )
        self.assertEqual(response.status_code, 403)

    async def test_register_nonexistent_channel(self):
        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 0)
        response = await sync_to_async(self.client.post)(
            "/api/channel/register", format="json", data={"channel_name": "@RTremblay"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 0)

    async def test_get_info_unauthenticated(self):
        self.assertEqual(await sync_to_async(Researcher.objects.count)(), 0)
        response = await sync_to_async(self.client.get)("/api/info/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.json()) > 0)
        self.assertTrue("name" in response.json())
        self.assertTrue("channel_name" in response.json())


class SubmitManuscriptTests(PaprDaemonAPITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = {
            "title": "My paper",
            "article": "my-paper",
            "claim_name": "my-paper_preprint",
            "authors": "Robert Tremblay",
            "corresponding_author": "@RTremblay",
            "revision": 1,
        }

    async def asyncSetUp(self):
        await super().asyncSetUp()

        tx = await self.daemon.jsonrpc_channel_create("@RTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)
        await self.daemon.channel_load("@RTremblay")

        response = await sync_to_async(self.client.post)(
            "/api/channel/register", format="json", data={"channel_name": "@RTremblay"}
        )
        self.assertEqual(response.status_code, 201)

        self.researcher = await sync_to_async(Researcher.objects.get)(
            channel_name="@RTremblay"
        )

        token = RefreshToken.for_user(self.researcher)
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {str(token.access_token)}"}
        self.client = APIClient(**self.headers)

    async def test_post_manuscript_valid(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=self.data, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 1)

        m = await sync_to_async(Manuscript.objects.latest)("pk")

        self.assertEqual(m.title, self.data["title"])
        self.assertEqual(m.claim_name, self.data["claim_name"])
        self.assertEqual(m.authors, self.data["authors"])

        self.assertEqual(
            await sync_to_async(
                SubmittedArticle.objects.filter(
                    corresponding_author__channel_name=self.data["corresponding_author"]
                ).count
            )(),
            1,
        )

    async def test_post_manuscript_valid_encrypted(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=True,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=self.data, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 1)

        m = await sync_to_async(Manuscript.objects.latest)("pk")

        self.assertEqual(m.title, self.data["title"])
        self.assertEqual(m.claim_name, self.data["claim_name"])
        self.assertEqual(m.authors, self.data["authors"])

        self.assertEqual(
            await sync_to_async(
                SubmittedArticle.objects.filter(
                    corresponding_author__channel_name=self.data["corresponding_author"]
                ).count
            )(),
            1,
        )

    async def test_post_manuscript_no_claim(self):
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=self.data, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

    async def test_post_manuscript_wrong_title(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        data = self.data.copy()
        data["title"] = "Our paper"
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=data, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

    async def test_post_manuscript_wrong_author(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        data = self.data.copy()
        data["authors"] = "Bob Tremblay"
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=data, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

    async def test_post_manuscript_wrong_author_encrypted(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=True,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        data = self.data.copy()
        data["authors"] = "Bob Tremblay"
        response = await sync_to_async(self.client.post)(
            f"/api/article/submit", data=data, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

    async def test_post_manuscript_other_channel_same_daemon(self):
        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        tx = await self.daemon.jsonrpc_channel_create("@BTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)

        response = await sync_to_async(self.client.post)(
            "/api/channel/register", format="json", data={"channel_name": "@BTremblay"}
        )
        self.assertEqual(response.status_code, 201)

        researcher = await sync_to_async(Researcher.objects.get)(
            channel_name="@BTremblay"
        )

        token = RefreshToken.for_user(researcher)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {str(token.access_token)}"}
        client = APIClient(**headers)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        response = await sync_to_async(client.post)(
            f"/api/article/submit", data=self.data, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.data)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)


class CompleteIntegrationTests(PaprDaemonAPITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = {
            "title": "My paper",
            "claim_name": "my-paper_preprint",
            "authors": "Robert Tremblay",
            "corresponding_author": "@RTremblay",
        }

    async def asyncSetUp(self):
        await super().asyncSetUp()

        tx = await self.daemon.jsonrpc_channel_create("@RTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)
        await self.daemon.channel_load("@RTremblay")

    async def test_submit_for_review(self):
        with self.mock_server():
            data = await self.daemon.papr_server_add("http://reviewserver.org")

        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
            server_name="Test Review Server",
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)
        self.assertEqual(await sync_to_async(SubmittedArticle.objects.count)(), 0)

        with self.mock_server():
            response = await self.daemon.papr_article_request_review(
                "my-paper", "Test Review Server"
            )

        self.assertEqual(response["status_code"], 201)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 1)
        self.assertEqual(await sync_to_async(SubmittedArticle.objects.count)(), 1)

        with self.mock_server():
            response = await self.daemon.papr_article_status(
                "my-paper"
            )
        self.assertIn('article', response)
        self.assertEqual(response['article']['revision'], 0)

    async def test_submit_for_review_invalid_manuscript(self):
        with self.mock_server():
            data = await self.daemon.papr_server_add("http://reviewserver.org")

        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

        with self.mock_server():
            response = await self.daemon.papr_article_request_review(
                "my-manuscript", "Test Review Server"
            )

        self.assertIn("error", response)
        self.assertIn("no such article found", response["error"])
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

    async def test_submit_for_review_invalid_claim(self):
        with self.mock_server():
            data = await self.daemon.papr_server_add("http://reviewserver.org")

        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)

        with Session(self.daemon.engine) as session:
            art = ClientArticle(
                base_claim_name="my-manuscript",
                channel_name="@RTremblay",
                reviewed=False,
                revision=0,
            )
            man = ClientManuscript(
                claim_name="my-manuscript",
                bid="1.0",
                title="My paper",
                abstract="we did great stuff",
                authors="Robert Tremblay",
                tags="test",
                article=art,
            )

            session.add(man)
            session.add(art)
            session.commit()

        with self.mock_server():
            response = await self.daemon.papr_article_request_review(
                "my-manuscript", "Test Review Server"
            )

        self.assertIn("error", response)
        self.assertIn("status_code", response)
        self.assertEqual(response["status_code"], 404)
        self.assertEqual(await sync_to_async(Manuscript.objects.count)(), 0)


class RecommendationTests(PaprDaemonAPITestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        tx = await self.daemon.jsonrpc_channel_create("@RTremblay", bid="1.0")
        await self.generate(1)
        await self.ledger.wait(tx, self.blockchain.block_expected)
        await self.daemon.channel_load("@RTremblay")

        with self.mock_server():
            data = await self.daemon.papr_server_add("http://reviewserver.org")

        self.researcher = await sync_to_async(Researcher.objects.get)(
            channel_name="@RTremblay"
        )

        daemon2 = await self.add_daemon()
        addresses = await daemon2.wallet_manager.default_account.receiving.get_addresses()
        await self.send_to_address_and_wait(addresses[0], 10, 1, ledger=daemon2.ledger)
        tx = await daemon2.jsonrpc_channel_create("@STremblay", bid="1.0")
        await self.generate(1)
        await daemon2.ledger.wait(tx, self.blockchain.block_expected)
        await daemon2.channel_load("@STremblay")

        with self.mock_server():
            data = await daemon2.papr_server_add("http://reviewserver.org")


        file_path = os.path.join(TESTS_DIR, "data", "document1.pdf")

        ret = await self.daemon.papr_article_create(
            base_claim_name="my-paper",
            bid="0.001",
            file_path=file_path,
            title="My paper",
            abstract="we did great stuff",
            authors="Robert Tremblay",
            tags=["test"],
            encrypt=False,
            server_name="Test Review Server",
        )

        await self.generate(1)
        await self.ledger.wait(ret["tx"], self.blockchain.block_expected)

        with self.mock_server():
            response = await self.daemon.papr_article_request_review(
                "my-paper", "Test Review Server"
            )
            self.assertNotIn("error", response)


    def tearDown(self):
        pass

    async def test_recommend_valid_reviewer(self):
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 0)
        with self.mock_server():
            ret = await self.daemon.papr_reviewer_recommend("my-paper_preprint", "Steve Tremblay", reviewer_channel="@STremblay")

        self.assertIn('info', ret)
        self.assertEqual(ret["status_code"], 201)
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 1)

    async def test_recommend_self(self):
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 0)
        with self.mock_server():
            ret = await self.daemon.papr_reviewer_recommend("my-paper_preprint", "Robert Tremblay", reviewer_channel="@RTremblay")

        self.assertIn('error', ret)
        self.assertEqual(ret["status_code"], 400)
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 0)

    async def test_recommend_twice(self):
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 0)
        with self.mock_server():
            ret = await self.daemon.papr_reviewer_recommend("my-paper_preprint", "Steve Tremblay", reviewer_channel="@STremblay")

        self.assertIn('info', ret)
        self.assertEqual(ret["status_code"], 201)
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 1)

        with self.mock_server():
            ret = await self.daemon.papr_reviewer_recommend("my-paper_preprint", "Steve Tremblay", reviewer_channel="@STremblay")

        self.assertIn('error', ret)
        self.assertEqual(ret["status_code"], 400)
        self.assertEqual(await sync_to_async(ReviewerRecommendation.objects.count)(), 1)
