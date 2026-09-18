from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lms", "0003_remove_anggotakelas_unik_anggota_kelas_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pengumpulantugas",
            name="dinilai_oleh",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="penilaian_diberikan",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]