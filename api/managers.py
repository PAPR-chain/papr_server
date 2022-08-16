from django.contrib.auth.base_user import BaseUserManager


class ResearcherManager(BaseUserManager):
    def create_user(self, channel_name, **extra_fields):
        if not channel_name:
            raise ValueError("A channel name must be provided")

        ### Verify that the channel exists

        researcher = self.model(channel_name=channel_name, **extra_fields)
        researcher.set_unusable_password()
        researcher.save()
        return researcher

    def create_superuser(self, channel_name, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """

        if not channel_name:
            raise ValueError("A channel name must be provided")

        return self.create_user(channel_name, **extra_fields)
