import os

import cloudinary.uploader
from cloudinary_storage.storage import MediaCloudinaryStorage


class CloudinaryVideoStorage(MediaCloudinaryStorage):
    RESOURCE_TYPE = 'video'
    CHUNK_THRESHOLD = 10 * 1024 * 1024
    CHUNK_SIZE = 6 * 1024 * 1024

    def _upload(self, name, content):
        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'tags': self.TAG,
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder

        if getattr(content, 'size', 0) > self.CHUNK_THRESHOLD:
            options['chunk_size'] = self.CHUNK_SIZE
            return cloudinary.uploader.upload_large(content, **options)

        return cloudinary.uploader.upload(content, **options)


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
