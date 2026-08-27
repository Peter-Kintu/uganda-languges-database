from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('eshop', '0019_product_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='impressions',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
    ]
