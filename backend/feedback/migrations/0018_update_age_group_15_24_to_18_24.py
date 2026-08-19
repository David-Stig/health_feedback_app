from django.db import migrations, models


OLD_AGE_GROUP = "15-24 years"
NEW_AGE_GROUP = "18-24 years"


def forwards_update_age_group(apps, schema_editor):
    Feedback = apps.get_model("feedback", "Feedback")
    Feedback.objects.filter(age_group=OLD_AGE_GROUP).update(age_group=NEW_AGE_GROUP)


def backwards_update_age_group(apps, schema_editor):
    Feedback = apps.get_model("feedback", "Feedback")
    Feedback.objects.filter(age_group=NEW_AGE_GROUP).update(age_group=OLD_AGE_GROUP)


class Migration(migrations.Migration):

    dependencies = [
        ("feedback", "0017_feedback_consent_acknowledged_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="age_group",
            field=models.CharField(
                blank=True,
                choices=[
                    ("18-24 years", "18-24 years"),
                    ("25-34 years", "25-34 years"),
                    ("35-49 years", "35-49 years"),
                    ("50-64 years", "50-64 years"),
                    ("65+ years", "65+ years"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(
            forwards_update_age_group,
            backwards_update_age_group,
        ),
    ]
