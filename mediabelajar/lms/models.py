from datetime import timedelta
import re

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        GADIK = "GADIK", "Gadik"
        SERDIK = "SERDIK", "Serdik"

    nama_lengkap = models.CharField(max_length=255, blank=True)
    nip_nrp = models.CharField(max_length=30, unique=True, null=True, blank=True)
    tempat_lahir = models.CharField(max_length=100, blank=True)
    tanggal_lahir = models.DateField(null=True, blank=True)
    asal_pengiriman = models.CharField(max_length=150, blank=True)
    alamat = models.TextField(blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.SERDIK)

    @property
    def display_name(self):
        return self.nama_lengkap or self.get_full_name() or self.username

    def __str__(self):
        return f"{self.display_name} - {self.get_role_display()}"


class Kurikulum(models.Model):
    nama_kurikulum = models.CharField(max_length=150)
    tahun_ajaran = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_active", "-tahun_ajaran", "nama_kurikulum"]
        verbose_name_plural = "Kurikulum"

    def __str__(self):
        return f"{self.nama_kurikulum} ({self.tahun_ajaran})"


class MataPelajaran(models.Model):
    kurikulum = models.ForeignKey(Kurikulum, on_delete=models.CASCADE, related_name="mata_pelajaran")
    kode_mapel = models.CharField(max_length=20)
    nama_mapel = models.CharField(max_length=100)
    gadik_pengajar = models.ManyToManyField(
        CustomUser,
        blank=True,
        limit_choices_to={"role": CustomUser.Role.GADIK},
        related_name="mata_pelajaran_diampu",
    )

    class Meta:
        ordering = ["kode_mapel"]
        constraints = [
            models.UniqueConstraint(fields=["kurikulum", "kode_mapel"], name="unik_kode_mapel_per_kurikulum")
        ]
        verbose_name_plural = "Mata pelajaran"

    def __str__(self):
        return f"{self.kode_mapel} - {self.nama_mapel}"


class Kelas(models.Model):
    nama_kelas = models.CharField(max_length=50)
    kurikulum = models.ForeignKey(Kurikulum, on_delete=models.PROTECT, related_name="kelas")
    gadik_pembina = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": CustomUser.Role.GADIK},
        related_name="kelas_binaan",
    )

    class Meta:
        ordering = ["nama_kelas"]
        verbose_name_plural = "Kelas"

    def __str__(self):
        return self.nama_kelas


class AnggotaKelas(models.Model):
    kelas = models.ForeignKey(Kelas, on_delete=models.CASCADE, related_name="anggota")
    serdik = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={"role": CustomUser.Role.SERDIK},
        related_name="keanggotaan_kelas",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["serdik"], name="unik_kelas_per_serdik")]
        verbose_name_plural = "Anggota kelas"

    def __str__(self):
        return f"{self.serdik.display_name} - {self.kelas}"


class ModulBelajar(models.Model):
    kelas = models.ForeignKey(Kelas, on_delete=models.CASCADE, related_name="modul")
    mapel = models.ForeignKey(MataPelajaran, on_delete=models.PROTECT, related_name="modul")
    gadik = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="modul_dibuat")
    judul = models.CharField(max_length=200)
    deskripsi = models.TextField()
    file_modul = models.FileField(upload_to="modul/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Modul belajar"

    def clean(self):
        if self.mapel_id and self.kelas_id and self.mapel.kurikulum_id != self.kelas.kurikulum_id:
            raise ValidationError({"mapel": "Mata pelajaran harus berasal dari kurikulum kelas."})

    def __str__(self):
        return self.judul


class Tugas(models.Model):
    kelas = models.ForeignKey(Kelas, on_delete=models.CASCADE, related_name="tugas")
    mapel = models.ForeignKey(MataPelajaran, on_delete=models.PROTECT, related_name="tugas")
    gadik = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="tugas_dibuat")
    judul_tugas = models.CharField(max_length=200)
    instruksi = models.TextField()
    file_lampiran = models.FileField(upload_to="tugas/lampiran/%Y/%m/", blank=True)
    deadline = models.DateTimeField()
    bobot = models.PositiveSmallIntegerField(default=100, help_text="Bobot nilai dalam persen.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deadline"]
        verbose_name_plural = "Tugas"

    def clean(self):
        if self.mapel_id and self.kelas_id and self.mapel.kurikulum_id != self.kelas.kurikulum_id:
            raise ValidationError({"mapel": "Mata pelajaran harus berasal dari kurikulum kelas."})
        if self.bobot > 100:
            raise ValidationError({"bobot": "Bobot tidak boleh lebih dari 100%."})

    @property
    def is_closed(self):
        return timezone.now() > self.deadline

    def __str__(self):
        return self.judul_tugas


class Ujian(models.Model):
    class Metode(models.TextChoices):
        ESAI = "ESAI", "Esai"
        PILIHAN_GANDA = "PILIHAN_GANDA", "Pilihan Ganda"

    kelas = models.ForeignKey(Kelas, on_delete=models.CASCADE, related_name="ujian")
    mapel = models.ForeignKey(MataPelajaran, on_delete=models.PROTECT, related_name="ujian")
    gadik = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="ujian_dibuat")
    judul = models.CharField(max_length=200)
    metode = models.CharField(max_length=20, choices=Metode.choices)
    instruksi = models.TextField()
    waktu_mulai = models.DateTimeField()
    waktu_selesai = models.DateTimeField()
    durasi_menit = models.PositiveSmallIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["waktu_mulai"]
        verbose_name_plural = "Ujian"

    def clean(self):
        if self.mapel_id and self.kelas_id and self.mapel.kurikulum_id != self.kelas.kurikulum_id:
            raise ValidationError({"mapel": "Mata pelajaran harus berasal dari kurikulum kelas."})
        if self.durasi_menit < 1:
            raise ValidationError({"durasi_menit": "Durasi ujian minimal 1 menit."})
        if self.waktu_mulai and self.waktu_selesai and self.waktu_selesai <= self.waktu_mulai:
            raise ValidationError({"waktu_selesai": "Batas akhir harus setelah waktu mulai ujian."})

    def save(self, *args, **kwargs):
        if not self.waktu_selesai and self.waktu_mulai:
            self.waktu_selesai = self.waktu_mulai + timedelta(minutes=self.durasi_menit)
        super().save(*args, **kwargs)

    @property
    def sudah_mulai(self):
        return timezone.now() >= self.waktu_mulai

    @property
    def sudah_selesai(self):
        return timezone.now() >= self.waktu_selesai

    @property
    def sedang_berlangsung(self):
        return self.sudah_mulai and not self.sudah_selesai

    def __str__(self):
        return self.judul


class SoalUjianEsai(models.Model):
    class Pemeriksaan(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        OTOMATIS = "OTOMATIS", "Otomatis"
        PENALARAN = "PENALARAN", "Penalaran"

    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE, related_name="soal_esai")
    urutan = models.PositiveSmallIntegerField()
    pertanyaan = models.TextField()
    kunci_jawaban = models.TextField()
    pemeriksaan = models.CharField(max_length=10, choices=Pemeriksaan.choices, default=Pemeriksaan.MANUAL)

    class Meta:
        ordering = ["urutan"]
        constraints = [
            models.UniqueConstraint(fields=["ujian", "urutan"], name="unik_urutan_soal_esai_per_ujian")
        ]
        verbose_name_plural = "Soal ujian esai"

    def clean(self):
        if self.ujian_id and self.ujian.metode != Ujian.Metode.ESAI:
            raise ValidationError({"ujian": "Soal esai hanya dapat ditambahkan ke ujian metode Esai."})
        if self.urutan < 1:
            raise ValidationError({"urutan": "Nomor soal minimal 1."})
    def __str__(self):
        return f"Soal {self.urutan} - {self.ujian}"


class SoalUjianPilihanGanda(models.Model):
    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE, related_name="soal_pilihan_ganda")
    urutan = models.PositiveSmallIntegerField()
    pertanyaan = models.TextField()

    class Meta:
        ordering = ["urutan"]
        constraints = [
            models.UniqueConstraint(fields=["ujian", "urutan"], name="unik_urutan_soal_pg_per_ujian")
        ]
        verbose_name_plural = "Soal ujian pilihan ganda"

    def clean(self):
        if self.ujian_id and self.ujian.metode != Ujian.Metode.PILIHAN_GANDA:
            raise ValidationError({"ujian": "Soal pilihan ganda hanya dapat ditambahkan ke ujian metode Pilihan Ganda."})
        if self.urutan < 1:
            raise ValidationError({"urutan": "Nomor soal minimal 1."})

    def __str__(self):
        return f"Soal {self.urutan} - {self.ujian}"


class OpsiUjianPilihanGanda(models.Model):
    soal = models.ForeignKey(SoalUjianPilihanGanda, on_delete=models.CASCADE, related_name="opsi")
    urutan = models.PositiveSmallIntegerField()
    teks = models.CharField(max_length=500)
    is_kunci = models.BooleanField(default=False)

    class Meta:
        ordering = ["urutan"]
        constraints = [
            models.UniqueConstraint(fields=["soal", "urutan"], name="unik_urutan_opsi_pg_per_soal")
        ]
        verbose_name_plural = "Opsi ujian pilihan ganda"

    def clean(self):
        if self.urutan < 1:
            raise ValidationError({"urutan": "Nomor opsi minimal 1."})

    def __str__(self):
        return f"Opsi {self.urutan} - {self.soal}"


class PengumpulanUjian(models.Model):
    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE, related_name="pengumpulan")
    serdik = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="pengumpulan_ujian")
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    nilai = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ujian", "serdik"], name="unik_pengumpulan_ujian")]
        verbose_name_plural = "Pengumpulan ujian"

    @staticmethod
    def _kata_kunci(teks):
        return set(re.findall(r"[a-z0-9]+", teks.casefold()))

    @classmethod
    def _rasio_otomatis(cls, kunci_jawaban, jawaban):
        kunci = cls._kata_kunci(kunci_jawaban)
        kata_jawaban = cls._kata_kunci(jawaban)
        if not kunci:
            return Decimal("0")
        rasio = Decimal(len(kunci & kata_jawaban)) / Decimal(len(kunci))
        jumlah_kata_hilang = len(kunci - kata_jawaban)
        if 1 <= jumlah_kata_hilang <= 3:
            toleransi = {
                1: Decimal("0.95"),
                2: Decimal("0.90"),
                3: Decimal("0.85"),
            }[jumlah_kata_hilang]
            return max(rasio, toleransi)
        return rasio

    @property
    def batas_waktu(self):
        if not self.started_at:
            return self.ujian.waktu_selesai
        batas_durasi = self.started_at + timedelta(minutes=self.ujian.durasi_menit)
        return min(batas_durasi, self.ujian.waktu_selesai)

    @property
    def waktu_habis(self):
        return timezone.now() >= self.batas_waktu

    @property
    def sudah_dikumpulkan(self):
        return self.submitted_at is not None

    @classmethod
    def rekomendasi_penalaran(cls, soal, jawaban, nilai_maksimal):
        kata_umum = {
            "yang", "dan", "atau", "dari", "untuk", "pada", "dengan", "adalah",
            "dalam", "ini", "itu", "karena", "maka", "sebagai", "oleh", "ke", "di",
        }
        acuan = (cls._kata_kunci(soal.pertanyaan) | cls._kata_kunci(soal.kunci_jawaban)) - kata_umum
        kata_jawaban = cls._kata_kunci(jawaban) - kata_umum
        relevansi = Decimal(len(acuan & kata_jawaban)) / Decimal(len(acuan)) if acuan else Decimal("0")
        elaborasi = min(Decimal(len(kata_jawaban)) / Decimal("30"), Decimal("1"))
        penanda = {"karena", "sehingga", "namun", "menurut", "contoh", "dampak", "alasan"}
        struktur = min(Decimal(len(cls._kata_kunci(jawaban) & penanda)) / Decimal("2"), Decimal("1"))
        kualitas = min(
            relevansi * Decimal("0.60") + elaborasi * Decimal("0.25") + struktur * Decimal("0.15"),
            Decimal("1"),
        )
        return (nilai_maksimal * kualitas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def nilai_otomatis(self):
        soal = list(self.ujian.soal_esai.all())
        if not soal:
            return None
        nilai_per_soal = Decimal("100") / Decimal(len(soal))
        jawaban_by_soal = {item.soal_id: item for item in self.jawaban_esai.all()}
        total_tanpa_pembulatan = Decimal("0")
        for item in soal:
            jawaban_obj = jawaban_by_soal.get(item.pk)
            jawaban_teks = jawaban_obj.jawaban if jawaban_obj else ""
            if item.pemeriksaan == SoalUjianEsai.Pemeriksaan.OTOMATIS:
                rasio = self._rasio_otomatis(item.kunci_jawaban, jawaban_teks)
                skor_tanpa_pembulatan = nilai_per_soal * rasio
            elif item.pemeriksaan == SoalUjianEsai.Pemeriksaan.PENALARAN:
                skor_tanpa_pembulatan = self.rekomendasi_penalaran(item, jawaban_teks, nilai_per_soal)
            else:
                continue
            skor = skor_tanpa_pembulatan.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if jawaban_obj:
                jawaban_obj.skor = skor
                jawaban_obj.skor_otomatis = skor
                jawaban_obj.save(update_fields=["skor", "skor_otomatis"])
            total_tanpa_pembulatan += skor_tanpa_pembulatan
        if all(item.pemeriksaan == SoalUjianEsai.Pemeriksaan.OTOMATIS for item in soal):
            self.nilai = min(total_tanpa_pembulatan, Decimal("100.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            self.save(update_fields=["nilai"])
        return self.nilai

    def nilai_pilihan_ganda(self):
        soal = list(self.ujian.soal_pilihan_ganda.prefetch_related("opsi"))
        if not soal:
            return None
        nilai_per_soal = Decimal("100") / Decimal(len(soal))
        jawaban_by_soal = {item.soal_id: item for item in self.jawaban_pilihan_ganda.select_related("opsi")}
        total_tanpa_pembulatan = Decimal("0")
        for item in soal:
            jawaban_obj = jawaban_by_soal.get(item.pk)
            skor_tanpa_pembulatan = Decimal("0")
            if jawaban_obj and jawaban_obj.opsi.is_kunci:
                skor_tanpa_pembulatan = nilai_per_soal
            skor = skor_tanpa_pembulatan.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if jawaban_obj:
                jawaban_obj.skor = skor
                jawaban_obj.save(update_fields=["skor"])
            total_tanpa_pembulatan += skor_tanpa_pembulatan
        self.nilai = min(total_tanpa_pembulatan, Decimal("100.00")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.save(update_fields=["nilai"])
        return self.nilai

    def __str__(self):
        return f"{self.serdik.display_name} - {self.ujian}"


class JawabanUjianEsai(models.Model):
    pengumpulan = models.ForeignKey(PengumpulanUjian, on_delete=models.CASCADE, related_name="jawaban_esai")
    soal = models.ForeignKey(SoalUjianEsai, on_delete=models.CASCADE, related_name="jawaban")
    jawaban = models.TextField()
    skor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    skor_otomatis = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    alasan_koreksi = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pengumpulan", "soal"], name="unik_jawaban_esai_per_soal")
        ]
        verbose_name_plural = "Jawaban ujian esai"

    def __str__(self):
        return f"Jawaban {self.pengumpulan.serdik.display_name} - soal {self.soal.urutan}"


class JawabanUjianPilihanGanda(models.Model):
    pengumpulan = models.ForeignKey(PengumpulanUjian, on_delete=models.CASCADE, related_name="jawaban_pilihan_ganda")
    soal = models.ForeignKey(SoalUjianPilihanGanda, on_delete=models.CASCADE, related_name="jawaban")
    opsi = models.ForeignKey(OpsiUjianPilihanGanda, on_delete=models.PROTECT, related_name="jawaban")
    skor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pengumpulan", "soal"], name="unik_jawaban_pg_per_soal")
        ]
        verbose_name_plural = "Jawaban ujian pilihan ganda"

    def clean(self):
        if self.opsi_id and self.soal_id and self.opsi.soal_id != self.soal_id:
            raise ValidationError({"opsi": "Opsi jawaban harus berasal dari soal yang sama."})

    def __str__(self):
        return f"Jawaban {self.pengumpulan.serdik.display_name} - soal {self.soal.urutan}"


class PengumpulanTugas(models.Model):
    class Status(models.TextChoices):
        TERKIRIM = "TERKIRIM", "Terkirim"
        TERLAMBAT = "TERLAMBAT", "Terlambat"
        DINILAI = "DINILAI", "Dinilai"

    tugas = models.ForeignKey(Tugas, on_delete=models.CASCADE, related_name="pengumpulan")
    serdik = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="pengumpulan_tugas")
    file_tugas = models.FileField(upload_to="pengumpulan/%Y/%m/")
    catatan_serdik = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    nilai = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    catatan_gadik = models.TextField(blank=True)
    dinilai_oleh = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="penilaian_diberikan",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TERKIRIM)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [models.UniqueConstraint(fields=["tugas", "serdik"], name="unik_pengumpulan_tugas")]
        verbose_name_plural = "Pengumpulan tugas"

    def clean(self):
        if self.serdik_id and self.serdik.role != CustomUser.Role.SERDIK:
            raise ValidationError({"serdik": "Pengumpulan hanya dapat dibuat oleh Serdik."})
        if self.nilai is not None and not 0 <= self.nilai <= 100:
            raise ValidationError({"nilai": "Nilai harus berada di antara 0 dan 100."})

    def save(self, *args, **kwargs):
        if self.nilai is not None:
            self.status = self.Status.DINILAI
        else:
            waktu_kirim = self.submitted_at or timezone.now()
            self.status = self.Status.TERLAMBAT if waktu_kirim > self.tugas.deadline else self.Status.TERKIRIM
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.serdik.display_name} - {self.tugas}"
