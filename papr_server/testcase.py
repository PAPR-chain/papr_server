import os
import logging
from io import StringIO
from asgiref.sync import sync_to_async
from rest_framework.test import APIClient

from django.core.management import call_command
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
