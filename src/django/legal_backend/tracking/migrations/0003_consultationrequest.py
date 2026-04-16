from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracking", "0002_event_user_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsultationRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("message", models.TextField(blank=True)),
                ("preferred_time", models.CharField(blank=True, max_length=120)),
                ("page", models.CharField(blank=True, max_length=100)),
                ("user_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("session_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("metadata", models.JSONField(default=dict)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
