from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracking", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="user_id",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
    ]
