from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0008_remove_conversation_participants_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='attachment',
            field=models.FileField(upload_to='message_attachments/', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='communitymessage',
            name='attachment',
            field=models.FileField(upload_to='message_attachments/', blank=True, null=True),
        ),
    ]
