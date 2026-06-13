from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0012_businessreel_cloudinary_public_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='youtubechannel',
            name='last_sync_error',
            field=models.TextField(blank=True, help_text='Stores the last YouTube sync error message for this channel.', null=True),
        ),
        migrations.AddField(
            model_name='youtubechannel',
            name='sync_error_code',
            field=models.CharField(blank=True, help_text='YouTube API error code or reason from the last sync attempt.', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='youtubechannel',
            name='requires_reauth',
            field=models.BooleanField(default=False, help_text='Set when this channel needs authorization or access revalidation.'),
        ),
    ]
