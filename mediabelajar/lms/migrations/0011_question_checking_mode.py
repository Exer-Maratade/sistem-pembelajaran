from django.db import migrations, models


def copy_checking_mode_to_questions(apps, schema_editor):
    SoalUjianEsai = apps.get_model("lms", "SoalUjianEsai")
    for soal in SoalUjianEsai.objects.select_related("ujian"):
        soal.pemeriksaan = soal.ujian.pemeriksaan
        soal.save(update_fields=["pemeriksaan"])


class Migration(migrations.Migration):
    dependencies = [("lms", "0010_align_schedules_to_wita")]

    operations = [
        migrations.AddField(
            model_name="soalujianesai",
            name="pemeriksaan",
            field=models.CharField(
                choices=[("MANUAL", "Manual"), ("OTOMATIS", "Otomatis"), ("PENALARAN", "Penalaran")],
                default="MANUAL",
                max_length=10,
            ),
        ),
        migrations.RunPython(copy_checking_mode_to_questions, migrations.RunPython.noop),
    ]