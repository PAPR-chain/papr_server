from rest_framework.test import APITestCase

from api import views
from api.models import *

from papr.utilities import generate_SECP256k1_keys, SECP_decrypt_text

class AuthenticationTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key, cls.public_key = generate_SECP256k1_keys("test")
        super().setUpClass()

    def setUp(self):
        self.researcher = Researcher.objects.create(full_name="Robert Tremblay", channel_name="@RTremblay", public_key=self.public_key)
        m = Manuscript.objects.create(claim_name="paper-tremblay", claim_id="123456", title="Theory of Everything", author_list="Robert Tremblay", corresponding_author=self.researcher)

    def tearDown(self):
        pass

    def test_get_manuscript_unauth(self):
        response = self.client.get("/api/manuscripts/paper-tremblay", format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['detail'], "Authentication credentials were not provided.")

    def test_get_token(self):
        response = self.client.get("/api/token/@RTremblay", format='json')
        self.assertIn('access', response.json())
        self.assertIn('refresh', response.json())
        self.assertIn('pub_key', response.json())
        self.assertEqual(response.status_code, 200)

    def test_use_token(self):
        response = self.client.get("/api/token/@RTremblay", format='json')

        token_access = SECP_decrypt_text(self.private_key, response.json()['pub_key'], response.json()['access'])
        token_refresh = SECP_decrypt_text(self.private_key, response.json()['pub_key'], response.json()['refresh'])

        response = self.client.get("/api/manuscripts/paper-tremblay", format='json', HTTP_AUTHORIZATION="Bearer "+token_access)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('title', data)
        self.assertEqual(data['title'], "Theory of Everything")

        self.assertIn('claim_name', data)
        self.assertEqual(data['claim_name'], "paper-tremblay")

        self.assertIn('claim_id', data)
        self.assertEqual(data['claim_id'], "123456")

        self.assertIn('author_list', data)
        self.assertEqual(data['author_list'], "Robert Tremblay")
        self.assertIn('corresponding_author', data)
        self.assertEqual(data['corresponding_author'], "@RTremblay")

    def test_decrypt_wrong_key(self):
        response = self.client.get("/api/token/@RTremblay", format='json')

        private_key, public_key = generate_SECP256k1_keys("snooper")

        with self.assertRaises(Exception):
            token_access = SECP_decrypt_text(private_key, response.json()['pub_key'], response.json()['access'])
        with self.assertRaises(Exception):
            token_refresh = SECP_decrypt_text(private_key, response.json()['pub_key'], response.json()['refresh'])


class ManuscriptTests(APITestCase):
    def setUp(self):
        self.researcher = Researcher.objects.create(full_name="Robert Tremblay", channel_name="@RTremblay")
        self.client.force_authenticate(self.researcher)

    def tearDown(self):
        pass

    def test_get_manuscripts_empty(self):
        response = self.client.get("/api/manuscripts/", format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_get_manuscripts_one(self):
        m = Manuscript.objects.create(claim_name="paper-tremblay", claim_id="123456", title="Theory of Everything", author_list="Robert Tremblay", corresponding_author=self.researcher)
        response = self.client.get("/api/manuscripts/", format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_manuscripts_multiple(self):
        m = Manuscript.objects.create(claim_name="paper-tremblay", claim_id="123456", title="Theory of Everything", author_list="Robert Tremblay", corresponding_author=self.researcher)
        m = Manuscript.objects.create(claim_name="paper2-tremblay", claim_id="123457", title="Correction to 'Theory of Everything'", author_list="Robert Tremblay", corresponding_author=self.researcher)
        response = self.client.get("/api/manuscripts/", format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_post_manuscript_author_valid(self):
        data = {
            "title": "My paper",
            "claim_name": "my-paper",
            "claim_id": "12345",
            "author_list": "Robert Tremblay",
            "corresponding_author": "@RTremblay",

        }
        self.assertEqual(Manuscript.objects.count(), 0)
        response = self.client.post(f"/api/manuscripts/{data['claim_name']}", data=data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Manuscript.objects.count(), 1)

        m = Manuscript.objects.latest('pk')

        self.assertEqual(m.title, data["title"])
        self.assertEqual(m.claim_name, data["claim_name"])
        self.assertEqual(m.claim_id, data["claim_id"])
        self.assertEqual(m.author_list, data["author_list"])
        self.assertEqual(m.corresponding_author.channel_name, data["corresponding_author"])

    def test_post_manuscript_author_not_registered(self):
        data = {
            "title": "My paper",
            "claim_name": "my-paper",
            "claim_id": "12345",
            "author_list": "Steve Bobbins",
            "corresponding_author": "@SteveB",

        }
        response = self.client.post(f"/api/manuscripts/{data['claim_name']}", data=data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("corresponding_author", response.json())


