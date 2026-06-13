from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_customuser_is_approved_customuser_user_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='post_ad_watch_count',
            field=models.PositiveIntegerField(default=0, help_text='Tracks how many times this user has viewed the job ad flow for post payout eligibility.', verbose_name='Job ad watch count'),
        ),
        migrations.CreateModel(
            name='PayoutRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('card_type', models.CharField(blank=True, max_length=50, null=True)),
                ('card_last4', models.CharField(blank=True, max_length=4, null=True)),
                ('bank_name', models.CharField(blank=True, max_length=150, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')], default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='payout_requests', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
