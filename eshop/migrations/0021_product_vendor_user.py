from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eshop', '0020_product_impressions'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='vendor_user',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to=settings.AUTH_USER_MODEL),
        ),
    ]
