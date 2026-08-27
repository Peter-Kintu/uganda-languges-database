from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('languages', '0013_jobpost_base_salary_jobpost_job_location_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobpost',
            name='impressions',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
    ]
