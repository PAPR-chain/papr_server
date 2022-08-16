from rest_framework.test import APITestCase

from api import views
from api.models import *

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
        response = self.client.post(f"/api/manuscripts/{data['claim_name']}", data=data, format='json')
        self.assertEqual(response.status_code, 201)

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

