from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0011_customuser_phone'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=120)),
                ('value', models.TextField()),
                ('source', models.CharField(default='conversation', max_length=40)),
                ('confidence', models.DecimalField(decimal_places=3, default=1, max_digits=4)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_memories', to='users.customuser')),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='AgentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('goal', models.TextField()),
                ('steps', models.JSONField(default=list)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('completed', 'Completed'), ('failed', 'Failed')], default='draft', max_length=20)),
                ('current_step', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_plans', to='users.customuser')),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='AgentResearchCitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=500)),
                ('title', models.CharField(max_length=500)),
                ('url', models.URLField(max_length=1000)),
                ('excerpt', models.TextField(blank=True)),
                ('retrieved_at', models.DateTimeField(auto_now_add=True)),
                ('plan', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='citations', to='users.agentplan')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_research', to='users.customuser')),
            ],
            options={'ordering': ['-retrieved_at']},
        ),
        migrations.AddConstraint(
            model_name='agentmemory',
            constraint=models.UniqueConstraint(fields=('user', 'key'), name='unique_agent_memory_key'),
        ),
    ]
