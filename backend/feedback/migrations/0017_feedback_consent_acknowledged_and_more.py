from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feedback", "0016_alter_feedback_category_alter_feedback_rating_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedback",
            name="consent_acknowledged",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="feedback",
            name="consent_version",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
