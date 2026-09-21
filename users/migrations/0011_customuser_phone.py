from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0010_customuser_allow_channel_invites_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='phone',
            field=models.CharField(blank=True, max_length=30, verbose_name='Phone number'),
        ),
    ]