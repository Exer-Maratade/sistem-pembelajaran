from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("lms", "0011_question_checking_mode")]

    operations = [
        migrations.RemoveField(model_name="ujian", name="pemeriksaan"),
    ]