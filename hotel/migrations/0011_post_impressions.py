from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hotel', '0010_alter_communitymessage_content_alter_message_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='impressions',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
