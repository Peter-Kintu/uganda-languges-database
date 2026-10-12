from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateIdentityStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=settings.PRIVATE_IDENTITY_ROOT,
            base_url='/private-identity-not-public/',
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )
