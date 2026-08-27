from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('languages', '0014_jobpost_impressions'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobpost',
            name='posted_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_posts', to=settings.AUTH_USER_MODEL),
        ),
    ]
