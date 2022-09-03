import os
import logging
import json
import re
import contextlib
from io import StringIO
from asgiref.sync import sync_to_async

from aioresponses import CallbackResult, aioresponses
from django.http import HttpRequest
from django.urls import resolve
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework.response import Response

from unittest import mock

from papr.testcase import PaprDaemonTestCase

log = logging.getLogger("sqlalchemy.engine.Engine").disabled = True


class PaprDaemonAPITestCase(PaprDaemonTestCase):
    def setUp(self):
        # Make sure not to pollute and flush a production database
        assert "PAPR_IS_TEST" in os.environ
        super().setUp()
        self.client = APIClient()

    async def asyncSetUp(self):
        await super().asyncSetUp()

        with mock.patch("sys.stdout", new=StringIO()) as std_out:
            await self.daemon.start()
            # PaprDaemonTestCase and APITestCase don't play nice with each other,
            # it is thus necessary to manually handle the test database.
            await sync_to_async(call_command)("migrate")

    async def asyncTearDown(self):
        await super().asyncTearDown()

        with mock.patch("sys.stdout", new=StringIO()) as std_out:
            await sync_to_async(call_command)("flush", "--no-input")

    async def process_request_post(self, url, *args, **kwargs):
        return await self.process_request(url, "POST", *args, **kwargs)

    async def process_request_get(self, url, *args, **kwargs):
        return await self.process_request(url, "GET", *args, **kwargs)

    async def process_request(self, url, method, *args, **kwargs):
        request = HttpRequest()
        request.method = method

        if 'json' in kwargs:
            request.data = kwargs["json"]
            request.META["CONTENT_TYPE"] = "application/json"
            request.META["CONTENT_LENGTH"] = len(json.dumps(request.POST))

        request.headers = self.daemon.headers
        request.content_type = "application/json"
        request.path = str(url).replace("http://reviewserver.org", "")
        for k, v in self.daemon.headers.items():
            request.META[k] = v

        res = resolve(request.path)

        resp = await sync_to_async(res.func)(request, *res.args, **res.kwargs)
        if isinstance(resp, Response):
            resp.render()

        return CallbackResult(
            method=method,
            status=resp.status_code,
            body=resp.content.decode(),
            content_type="application/json",
        )

    @contextlib.contextmanager
    def mock_server(self):
        # Apparently, the aioresponses context messes with some part of the test runner
        # and cannot be used implicitly all the time.
        with aioresponses() as m:
            pat = re.compile(r"^http://reviewserver.org/.*$")
            m.post(pat, callback=self.process_request_post)
            m.get(pat, callback=self.process_request_get)
            yield

