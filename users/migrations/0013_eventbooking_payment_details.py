from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0012_agentmemory_agentplan_agentresearchcitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventbooking',
            name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='eventbooking',
            name='balance_due',
            field=models.DecimalField(decimal_places=2, default=50000, max_digits=10),
        ),
        migrations.AddField(
            model_name='eventbooking',
            name='payment_method',
            field=models.CharField(choices=[('PAID', 'Paid in full'), ('PROMO', 'Promo code'), ('INSTALLMENT', 'Installment')], default='PAID', max_length=12),
        ),
        migrations.AddField(
            model_name='eventbooking',
            name='promo_code',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
