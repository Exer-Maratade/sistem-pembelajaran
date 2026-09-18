from datetime import timedelta

from django.db import migrations, models


def populate_exam_timing(apps, schema_editor):
    Ujian = apps.get_model("lms", "Ujian")
    PengumpulanUjian = apps.get_model("lms", "PengumpulanUjian")
    for ujian in Ujian.objects.all():
        ujian.waktu_selesai = ujian.waktu_mulai + timedelta(minutes=ujian.durasi_menit)
        ujian.save(update_fields=["waktu_selesai"])
    for pengumpulan in PengumpulanUjian.objects.all():
        pengumpulan.started_at = pengumpulan.submitted_at
        pengumpulan.save(update_fields=["started_at"])


class Migration(migrations.Migration):
    dependencies = [("lms", "0012_remove_ujian_pemeriksaan")]

    operations = [
        migrations.AddField(
            model_name="ujian",
            name="waktu_selesai",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="pengumpulanujian",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="pengumpulanujian",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_exam_timing, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ujian",
            name="waktu_selesai",
            field=models.DateTimeField(),
        ),
    ]