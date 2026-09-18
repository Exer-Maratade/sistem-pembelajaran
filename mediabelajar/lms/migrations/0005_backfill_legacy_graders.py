from django.db import migrations


def backfill_legacy_graders(apps, schema_editor):
    PengumpulanTugas = apps.get_model("lms", "PengumpulanTugas")
    pengumpulan_lama = PengumpulanTugas.objects.filter(
        nilai__isnull=False,
        dinilai_oleh__isnull=True,
    ).select_related("tugas")

    for pengumpulan in pengumpulan_lama.iterator():
        pengumpulan.dinilai_oleh_id = pengumpulan.tugas.gadik_id
        pengumpulan.save(update_fields=["dinilai_oleh"])


class Migration(migrations.Migration):
    dependencies = [
        ("lms", "0004_pengumpulantugas_dinilai_oleh"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_graders, migrations.RunPython.noop),
    ]