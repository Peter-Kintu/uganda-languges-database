from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hotel', '0011_post_impressions'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedImpression',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, max_length=40)),
                ('content_type', models.CharField(choices=[('post', 'Post'), ('product', 'Product'), ('job', 'Job')], max_length=10)),
                ('object_id', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('viewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('viewer', 'session_key', 'content_type', 'object_id'), name='unique_feed_impression_per_session'),
                ],
            },
        ),
    ]
