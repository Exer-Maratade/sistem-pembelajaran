from datetime import timedelta

from django.db import migrations
from django.db.models import F


def align_schedules_to_wita(apps, schema_editor):
    Tugas = apps.get_model("lms", "Tugas")
    Ujian = apps.get_model("lms", "Ujian")
    adjustment = timedelta(hours=-1)
    Tugas.objects.update(deadline=F("deadline") + adjustment)
    Ujian.objects.update(waktu_mulai=F("waktu_mulai") + adjustment)


def restore_schedules_to_wib(apps, schema_editor):
    Tugas = apps.get_model("lms", "Tugas")
    Ujian = apps.get_model("lms", "Ujian")
    adjustment = timedelta(hours=1)
    Tugas.objects.update(deadline=F("deadline") + adjustment)
    Ujian.objects.update(waktu_mulai=F("waktu_mulai") + adjustment)


class Migration(migrations.Migration):
    dependencies = [("lms", "0009_remove_soalujianesai_bobot")]

    operations = [
        migrations.RunPython(align_schedules_to_wita, restore_schedules_to_wib),
    ]