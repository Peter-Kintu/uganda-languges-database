from pathlib import Path

from cloudinary_storage.storage import MediaCloudinaryStorage


class MessageAttachmentCloudinaryStorage(MediaCloudinaryStorage):
    IMAGE_EXTENSIONS = {'.avif', '.bmp', '.gif', '.jpeg', '.jpg', '.png', '.svg', '.tif', '.tiff', '.webp'}
    VIDEO_EXTENSIONS = {'.3gp', '.avi', '.m4v', '.mkv', '.mov', '.mp4', '.mpeg', '.mpg', '.ogv', '.webm', '.wmv'}

    @classmethod
    def resource_type_for_filename(cls, name):
        extension = Path(name).suffix.lower()
        if extension in cls.IMAGE_EXTENSIONS:
            return 'image'
        if extension in cls.VIDEO_EXTENSIONS:
            return 'video'
        return 'raw'

    def _get_resource_type(self, name):
        parts = Path(name).parts
        try:
            attachment_index = parts.index('message_attachments')
        except ValueError:
            return 'image'
        if attachment_index + 1 < len(parts):
            resource_type = parts[attachment_index + 1]
            if resource_type in {'image', 'video', 'raw'}:
                return resource_type
        return 'image'


def message_attachment_upload_path(instance, filename):
    resource_type = MessageAttachmentCloudinaryStorage.resource_type_for_filename(filename)
    return f'message_attachments/{resource_type}/{filename}'
