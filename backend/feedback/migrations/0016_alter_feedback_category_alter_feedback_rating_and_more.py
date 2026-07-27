from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def backfill_legacy_rating_responses(apps, schema_editor):
    Feedback = apps.get_model("feedback", "Feedback")
    RatingResponse = apps.get_model("feedback", "RatingResponse")

    pending = []
    for entry in Feedback.objects.exclude(category="").exclude(rating__isnull=True):
        if RatingResponse.objects.filter(submission_id=entry.pk, category=entry.category).exists():
            continue
        pending.append(
            RatingResponse(
                submission_id=entry.pk,
                category=entry.category,
                rating=entry.rating,
                comment=entry.comment or "",
            )
        )

    if pending:
        RatingResponse.objects.bulk_create(pending, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("feedback", "0015_collectionsession_feedback_captured_by_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="category",
            field=models.CharField(blank=True, choices=[("Waiting time before being seen", "Waiting time before being seen"), ("Respect and dignity from staff", "Respect and dignity from staff"), ("Cleanliness of the health facility", "Cleanliness of the health facility"), ("Explanation of your illness and treatment", "Explanation of your illness and treatment"), ("Availability of Medication", "Availability of Medication")], max_length=64),
        ),
        migrations.AlterField(
            model_name="feedback",
            name="rating",
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.CreateModel(
            name="RatingResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("Waiting time before being seen", "Waiting time before being seen"), ("Respect and dignity from staff", "Respect and dignity from staff"), ("Cleanliness of the health facility", "Cleanliness of the health facility"), ("Explanation of your illness and treatment", "Explanation of your illness and treatment"), ("Availability of Medication", "Availability of Medication")], max_length=64)),
                ("rating", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rating_responses", to="feedback.feedback")),
            ],
            options={
                "ordering": ["created_at", "pk"],
                "indexes": [
                    models.Index(fields=["submission", "category"], name="feedback_rat_submiss_c9f0b1_idx"),
                    models.Index(fields=["category"], name="feedback_rat_categor_5017fe_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="ratingresponse",
            constraint=models.UniqueConstraint(fields=("submission", "category"), name="unique_rating_category_per_submission"),
        ),
        migrations.RunPython(backfill_legacy_rating_responses, migrations.RunPython.noop),
    ]
