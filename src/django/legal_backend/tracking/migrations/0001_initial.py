from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("page", models.CharField(db_index=True, max_length=100)),
                ("step", models.CharField(blank=True, max_length=100)),
                ("section", models.CharField(blank=True, max_length=100)),
                ("action", models.CharField(db_index=True, max_length=100)),
                ("service", models.CharField(blank=True, db_index=True, max_length=100)),
                ("target", models.CharField(blank=True, max_length=255)),
                ("session_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("url", models.URLField(blank=True)),
                ("referrer", models.URLField(blank=True)),
                ("user_agent", models.TextField(blank=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("metadata", models.JSONField(default=dict)),
            ],
            options={
                "ordering": ("-timestamp",),
            },
        ),
    ]
