from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feedback", "0019_rename_feedback_rat_submiss_c9f0b1_idx_feedback_ra_submiss_bb2f9c_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="no_insurance_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("I do not have any health insurance", "I do not have any health insurance"),
                    ("I have NHIMA, but I forgot my card / number", "I have NHIMA, but I forgot my card / number"),
                    ("I have private insurance, but I forgot my card / number", "I have private insurance, but I forgot my card / number"),
                    ("I have NHIMA, but the facility did not accept it", "I have NHIMA, but the facility did not accept it"),
                    ("I have private insurance, but this health post does not accept it ", "I have private insurance, but this health post does not accept it "),
                    ("My insurance does not cover the services I needed today", "My insurance does not cover the services I needed today"),
                    ("I have health insurance, but I did not need to use it", "I have health insurance, but I did not need to use it"),
                    ("I chose to pay out-of-pocket instead", "I chose to pay out-of-pocket instead"),
                    ("Not sure", "Not sure"),
                    ("Other", "Other"),
                ],
                max_length=128,
            ),
        ),
    ]
