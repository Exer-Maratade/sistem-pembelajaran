from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import TugasForm
from .models import AnggotaKelas, CustomUser, JawabanUjianEsai, JawabanUjianPilihanGanda, Kelas, Kurikulum, MataPelajaran, ModulBelajar, OpsiUjianPilihanGanda, PengumpulanTugas, PengumpulanUjian, SoalUjianEsai, SoalUjianPilihanGanda, Tugas, Ujian


class LmsWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gadik = CustomUser.objects.create_user(
            username="gadik", password="rahasia123", role=CustomUser.Role.GADIK, nama_lengkap="Gadik Utama"
        )
        cls.admin = CustomUser.objects.create_user(
            username="admin-test",
            password="rahasia123",
            role=CustomUser.Role.ADMIN,
            nama_lengkap="Admin Pengelola",
            is_staff=True,
        )
        cls.gadik_lain = CustomUser.objects.create_user(
            username="gadiklain", password="rahasia123", role=CustomUser.Role.GADIK
        )
        cls.serdik = CustomUser.objects.create_user(
            username="serdik", password="rahasia123", role=CustomUser.Role.SERDIK, nama_lengkap="Serdik Satu"
        )
        cls.serdik_lain = CustomUser.objects.create_user(
            username="serdiklain", password="rahasia123", role=CustomUser.Role.SERDIK
        )
        cls.kurikulum = Kurikulum.objects.create(nama_kurikulum="Kurikulum Presisi", tahun_ajaran="2026/2027")
        cls.kurikulum_lain = Kurikulum.objects.create(nama_kurikulum="Kurikulum Lain", tahun_ajaran="2026/2027")
        cls.mapel = MataPelajaran.objects.create(
            kurikulum=cls.kurikulum, kode_mapel="KAM-01", nama_mapel="Keamanan"
        )
        cls.mapel_lain = MataPelajaran.objects.create(
            kurikulum=cls.kurikulum_lain, kode_mapel="ETK-01", nama_mapel="Etika"
        )
        cls.mapel.gadik_pengajar.add(cls.gadik)
        cls.mapel_lain.gadik_pengajar.add(cls.gadik_lain)
        cls.kelas = Kelas.objects.create(
            nama_kelas="Kelas A", kurikulum=cls.kurikulum, gadik_pembina=cls.gadik
        )
        cls.kelas_lain = Kelas.objects.create(
            nama_kelas="Kelas B", kurikulum=cls.kurikulum, gadik_pembina=cls.gadik_lain
        )
        AnggotaKelas.objects.create(kelas=cls.kelas, serdik=cls.serdik)
        AnggotaKelas.objects.create(kelas=cls.kelas_lain, serdik=cls.serdik_lain)
        cls.tugas = Tugas.objects.create(
            kelas=cls.kelas,
            mapel=cls.mapel,
            gadik=cls.gadik,
            judul_tugas="Analisis Kasus",
            instruksi="Kerjakan analisis.",
            deadline=timezone.now() + timedelta(days=1),
        )

    def setUp(self):
        self.client.force_login(self.serdik)

    def test_dashboard_and_class_are_limited_to_student_membership(self):
        self.mapel.gadik_pengajar.add(self.gadik_lain)
        modul = ModulBelajar.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Modul Keamanan Dasar",
            deskripsi="Materi dasar keamanan untuk Serdik.",
            file_modul=SimpleUploadedFile("keamanan.pdf", b"materi", content_type="application/pdf"),
        )
        modul_lanjutan = ModulBelajar.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Modul Keamanan Lanjutan",
            deskripsi="Materi lanjutan keamanan untuk Serdik.",
            file_modul=SimpleUploadedFile("keamanan-lanjutan.pdf", b"materi", content_type="application/pdf"),
        )
        kelas_kurikulum_lain = Kelas.objects.create(
            nama_kelas="Kelas Kurikulum Lain",
            kurikulum=self.kurikulum_lain,
            gadik_pembina=self.gadik_lain,
        )
        modul_mapel_lain = ModulBelajar.objects.create(
            kelas=kelas_kurikulum_lain,
            mapel=self.mapel_lain,
            gadik=self.gadik_lain,
            judul="Modul Etika untuk Semua",
            deskripsi="Materi yang dapat diakses seluruh Serdik.",
            file_modul=SimpleUploadedFile("etika-semua.pdf", b"materi", content_type="application/pdf"),
        )
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'data-bs-target="#logoutConfirmModal"')
        self.assertContains(response, "Apakah Anda yakin ingin logout")
        self.assertContains(response, "Ya, Logout")
        self.assertContains(response, "Kelas A")
        self.assertNotContains(response, "Kelas B")
        self.assertContains(response, self.mapel.nama_mapel)
        self.assertContains(response, self.gadik.display_name)

        detail_kelas = self.client.get(reverse("detail_kelas", args=[self.kelas.pk]))
        self.assertEqual(detail_kelas.status_code, 200)
        self.assertContains(detail_kelas, self.mapel.nama_mapel)
        self.assertContains(detail_kelas, f"Dibuat oleh {self.gadik.display_name}")
        self.assertContains(detail_kelas, "Mata Pelajaran")
        self.assertContains(detail_kelas, "Gadik")
        self.assertContains(detail_kelas, modul.judul)
        self.assertContains(detail_kelas, modul_lanjutan.judul)
        self.assertEqual(len(detail_kelas.context["modul_per_mapel"]), 1)
        self.assertEqual(len(detail_kelas.context["modul_per_mapel"][0]["modul"]), 2)
        self.assertSetEqual(
            {gadik.pk for gadik in detail_kelas.context["modul_per_mapel"][0]["gadik"]},
            {self.gadik.pk, self.gadik_lain.pk},
        )
        self.assertContains(detail_kelas, self.gadik_lain.display_name)
        self.assertContains(detail_kelas, f'data-mapel-id="{self.mapel.pk}"', count=1)
        self.assertContains(detail_kelas, modul.file_modul.url, count=2)
        self.assertContains(detail_kelas, modul_lanjutan.file_modul.url, count=2)
        self.assertContains(detail_kelas, ">Lihat</a>")
        self.assertContains(detail_kelas, ">Download</a>")

        katalog_modul = self.client.get(reverse("daftar_modul"))
        self.assertEqual(katalog_modul.status_code, 200)
        self.assertContains(katalog_modul, self.mapel.nama_mapel)
        self.assertContains(katalog_modul, self.mapel_lain.nama_mapel)
        self.assertContains(katalog_modul, modul.judul)
        self.assertContains(katalog_modul, modul_lanjutan.judul)
        self.assertContains(katalog_modul, modul_mapel_lain.judul)
        self.assertContains(katalog_modul, f'data-mapel-id="{self.mapel.pk}"', count=1)
        self.assertNotContains(katalog_modul, "Tambah Modul")

        detail_tugas = self.client.get(reverse("detail_tugas", args=[self.tugas.pk]))
        self.assertContains(detail_tugas, self.mapel.nama_mapel)
        self.assertContains(detail_tugas, f"Dibuat oleh {self.gadik.display_name}")
        self.assertEqual(self.client.get(reverse("detail_kelas", args=[self.kelas_lain.pk])).status_code, 404)

    def test_student_cannot_open_teacher_workflow(self):
        self.assertEqual(self.client.get(reverse("buat_modul")).status_code, 403)
        self.assertEqual(self.client.get(reverse("buat_tugas")).status_code, 403)
        self.assertEqual(self.client.get(reverse("buat_ujian")).status_code, 403)
        self.assertEqual(self.client.get(reverse("daftar_pengumpulan", args=[self.tugas.pk])).status_code, 403)

    def test_admin_can_open_all_management_workflows(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian untuk Dikelola Admin",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab soal.",
            waktu_mulai=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.admin)

        for url in [
            reverse("daftar_modul"),
            reverse("buat_tugas"),
            reverse("daftar_ujian"),
            reverse("buat_ujian"),
            reverse("ubah_tugas", args=[self.tugas.pk]),
            reverse("daftar_pengumpulan", args=[self.tugas.pk]),
            reverse("ubah_ujian", args=[ujian.pk]),
            reverse("kelola_soal_esai", args=[ujian.pk]),
            reverse("hasil_ujian", args=[ujian.pk]),
            reverse("daftar_nilai"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        dashboard = self.client.get(reverse("dashboard"))
        for url in [
            reverse("daftar_modul"),
            reverse("daftar_ujian"),
            reverse("buat_tugas"),
            reverse("daftar_nilai"),
        ]:
            self.assertContains(dashboard, f'href="{url}"')
        daftar_ujian = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar_ujian, reverse("ubah_ujian", args=[ujian.pk]))
        detail_tugas = self.client.get(reverse("detail_tugas", args=[self.tugas.pk]))
        self.assertContains(detail_tugas, reverse("daftar_pengumpulan", args=[self.tugas.pk]))

        tugas_form = self.client.get(reverse("buat_tugas")).context["form"]
        self.assertSetEqual(set(tugas_form.fields["kelas"].queryset), {self.kelas, self.kelas_lain})
        self.assertSetEqual(set(tugas_form.fields["mapel"].queryset), {self.mapel, self.mapel_lain})

    def test_teacher_creates_exam_with_method_and_student_sees_own_class_only(self):
        self.client.force_login(self.gadik)
        form_response = self.client.get(reverse("buat_ujian"))
        self.assertContains(form_response, "Esai")
        self.assertContains(form_response, "Pilihan Ganda")

        response = self.client.post(
            reverse("buat_ujian"),
            {
                "kelas": self.kelas.pk,
                "mapel": self.mapel.pk,
                "judul": "Ujian Keamanan",
                "metode": Ujian.Metode.PILIHAN_GANDA,
                "instruksi": "Pilih jawaban yang paling tepat.",
                "waktu_mulai": (timezone.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                "waktu_selesai": (timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
                "durasi_menit": 90,
            },
        )
        self.assertRedirects(response, reverse("daftar_ujian"))
        ujian = Ujian.objects.get(judul="Ujian Keamanan")
        self.assertEqual(ujian.metode, Ujian.Metode.PILIHAN_GANDA)

        Ujian.objects.create(
            kelas=self.kelas_lain,
            mapel=self.mapel_lain,
            gadik=self.gadik_lain,
            judul="Ujian Kelas Lain",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab pertanyaan.",
            waktu_mulai=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.serdik)
        response = self.client.get(reverse("daftar_ujian"))
        self.assertContains(response, "Ujian Keamanan")
        self.assertContains(response, "Pilihan Ganda")
        self.assertNotContains(response, "Ujian Kelas Lain")

    def test_exam_owner_can_edit_exam_settings(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Lama",
            metode=Ujian.Metode.ESAI,
            instruksi="Instruksi lama.",
            waktu_mulai=timezone.now() + timedelta(hours=2),
            durasi_menit=60,
        )
        self.client.force_login(self.gadik)
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, reverse("ubah_ujian", args=[ujian.pk]))
        form_response = self.client.get(reverse("ubah_ujian", args=[ujian.pk]))
        self.assertNotIn("pemeriksaan", form_response.context["form"].fields)
        response = self.client.post(
            reverse("ubah_ujian", args=[ujian.pk]),
            {
                "kelas": self.kelas.pk,
                "mapel": self.mapel.pk,
                "judul": "Ujian Baru",
                "metode": Ujian.Metode.ESAI,
                "instruksi": "Instruksi baru.",
                "waktu_mulai": (timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
                "waktu_selesai": (timezone.now() + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
                "durasi_menit": 90,
            },
        )
        self.assertRedirects(response, reverse("daftar_ujian"))
        ujian.refresh_from_db()
        self.assertEqual(ujian.judul, "Ujian Baru")
        self.client.force_login(self.gadik_lain)
        self.assertEqual(self.client.get(reverse("ubah_ujian", args=[ujian.pk])).status_code, 404)

    def test_subject_teacher_can_see_and_edit_exam_created_by_other_teacher(self):
        self.mapel.gadik_pengajar.add(self.gadik_lain)
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Kolaboratif",
            metode=Ujian.Metode.ESAI,
            instruksi="Instruksi awal.",
            waktu_mulai=timezone.now() + timedelta(hours=2),
            durasi_menit=60,
        )

        self.client.force_login(self.gadik_lain)
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, "Ujian Kolaboratif")
        self.assertContains(daftar, reverse("ubah_ujian", args=[ujian.pk]))

        form_response = self.client.get(reverse("ubah_ujian", args=[ujian.pk]))
        self.assertEqual(form_response.status_code, 200)
        response = self.client.post(
            reverse("ubah_ujian", args=[ujian.pk]),
            {
                "kelas": self.kelas.pk,
                "mapel": self.mapel.pk,
                "judul": "Ujian Kolaboratif Diperbarui",
                "metode": Ujian.Metode.ESAI,
                "instruksi": "Instruksi diperbarui.",
                "waktu_mulai": (timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
                "waktu_selesai": (timezone.now() + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
                "durasi_menit": 90,
            },
        )
        self.assertRedirects(response, reverse("daftar_ujian"))
        ujian.refresh_from_db()
        self.assertEqual(ujian.judul, "Ujian Kolaboratif Diperbarui")

    def test_automatic_essay_grading_splits_100_equally(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Otomatis",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab semua soal.",
            waktu_mulai=timezone.now() - timedelta(minutes=5),
            durasi_menit=60,
        )
        soal_satu = SoalUjianEsai.objects.create(
            ujian=ujian,
            urutan=1,
            pertanyaan="Sebutkan warna bendera.",
            kunci_jawaban="merah putih",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.OTOMATIS,
        )
        soal_dua = SoalUjianEsai.objects.create(
            ujian=ujian,
            urutan=2,
            pertanyaan="Sebutkan kondisi ideal.",
            kunci_jawaban="aman tertib",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.OTOMATIS,
        )
        daftar_response = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar_response, "Mulai Ujian?")
        self.assertContains(daftar_response, "Ya, Mulai Ujian")
        self.assertRedirects(
            self.client.post(reverse("mulai_ujian_esai", args=[ujian.pk])),
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
        )
        form_response = self.client.get(reverse("kerjakan_ujian_esai", args=[ujian.pk]))
        self.assertContains(form_response, "Konfirmasi Pengumpulan Ujian")
        self.assertContains(form_response, "Ya, Kumpulkan")
        self.assertContains(form_response, "Peta soal")
        self.assertContains(form_response, "data-answered-count", html=False)
        self.assertContains(form_response, "data-total-count", html=False)
        self.assertContains(form_response, "data-open-submit-modal disabled", html=False)
        self.assertContains(form_response, "data-draft-key", html=False)
        self.assertContains(form_response, "localStorage.setItem(draftKey", html=False)
        self.assertContains(form_response, 'data-bs-target="#submitExamConfirmModal"')
        response = self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {f"soal_{soal_satu.pk}": "Merah dan putih"},
        )
        self.assertEqual(response.status_code, 200)
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertIsNone(pengumpulan.submitted_at)
        self.assertFalse(pengumpulan.jawaban_esai.exists())
        response = self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {f"soal_{soal_satu.pk}": "Merah dan putih", f"soal_{soal_dua.pk}": "Aman"},
        )
        self.assertRedirects(response, reverse("daftar_ujian"))
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertEqual(pengumpulan.nilai, Decimal("97.50"))
        self.assertEqual(
            list(JawabanUjianEsai.objects.filter(pengumpulan=pengumpulan).order_by("soal__urutan").values_list("skor", flat=True)),
            [Decimal("50.00"), Decimal("47.50")],
        )
        jawaban_kedua = JawabanUjianEsai.objects.get(pengumpulan=pengumpulan, soal=soal_dua)
        jawaban_kedua.jawaban = "aman dan tertib"
        jawaban_kedua.save(update_fields=["jawaban"])
        self.assertEqual(pengumpulan.nilai_otomatis(), 100)

    def test_automatic_essay_grading_tolerates_minor_missing_words_and_punctuation(self):
        self.assertEqual(
            PengumpulanUjian._rasio_otomatis(
                "Kerahasiaan, integritas, ketersediaan, autentikasi.",
                "kerahasiaan integritas ketersediaan",
            ),
            Decimal("0.95"),
        )
        self.assertEqual(
            PengumpulanUjian._rasio_otomatis(
                "Kerahasiaan, integritas, ketersediaan, autentikasi.",
                "Kerahasiaan integritas ketersediaan autentikasi",
            ),
            Decimal("1"),
        )
        self.assertEqual(
            PengumpulanUjian._rasio_otomatis(
                "merah putih aman tertib disiplin patroli",
                "merah putih",
            ),
            Decimal("0.3333333333333333333333333333"),
        )

    def test_multiple_choice_questions_use_configurable_options_and_auto_score(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Pilihan Ganda",
            metode=Ujian.Metode.PILIHAN_GANDA,
            instruksi="Pilih jawaban yang tepat.",
            waktu_mulai=timezone.now() - timedelta(minutes=5),
            durasi_menit=60,
        )
        self.client.force_login(self.gadik)
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]))
        form_response = self.client.get(reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]))
        self.assertContains(form_response, "Jumlah opsi")
        response = self.client.post(
            reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]),
            {
                "urutan": 1,
                "pertanyaan": "Apa warna bendera Indonesia?",
                "jumlah_opsi": 3,
                "opsi_1": "Merah biru",
                "opsi_2": "Merah putih",
                "opsi_3": "Putih hijau",
                "kunci_jawaban": "2",
            },
        )
        self.assertRedirects(response, reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]))
        soal_satu = SoalUjianPilihanGanda.objects.get(ujian=ujian, urutan=1)
        self.assertEqual(soal_satu.opsi.count(), 3)
        self.assertEqual(soal_satu.opsi.get(is_kunci=True).teks, "Merah putih")
        response = self.client.post(
            reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]),
            {
                "urutan": 2,
                "pertanyaan": "Manakah contoh sikap disiplin?",
                "jumlah_opsi": 4,
                "opsi_1": "Datang tepat waktu",
                "opsi_2": "Menunda tugas",
                "opsi_3": "Mengabaikan aturan",
                "opsi_4": "Tidak hadir",
                "kunci_jawaban": "1",
            },
        )
        self.assertRedirects(response, reverse("kelola_soal_pilihan_ganda", args=[ujian.pk]))
        soal_dua = SoalUjianPilihanGanda.objects.get(ujian=ujian, urutan=2)

        self.client.force_login(self.serdik)
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, "Mulai Ujian")
        self.assertRedirects(
            self.client.post(reverse("mulai_ujian_esai", args=[ujian.pk])),
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
        )
        form_response = self.client.get(reverse("kerjakan_ujian_esai", args=[ujian.pk]))
        self.assertContains(form_response, "UJIAN PILIHAN GANDA")
        self.assertContains(form_response, "Peta soal")
        self.assertContains(form_response, "data-answered-count", html=False)
        self.assertContains(form_response, "data-total-count", html=False)
        self.assertContains(form_response, "data-open-submit-modal disabled", html=False)
        self.assertContains(form_response, "data-draft-key", html=False)
        self.assertContains(form_response, "localStorage.setItem(draftKey", html=False)
        self.assertEqual(self.client.get(reverse("hasil_ujian", args=[ujian.pk])).status_code, 404)
        response = self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {f"soal_{soal_satu.pk}": soal_satu.opsi.get(is_kunci=True).pk},
        )
        self.assertEqual(response.status_code, 200)
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertIsNone(pengumpulan.submitted_at)
        self.assertFalse(pengumpulan.jawaban_pilihan_ganda.exists())
        response = self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {
                f"soal_{soal_satu.pk}": soal_satu.opsi.get(is_kunci=True).pk,
                f"soal_{soal_dua.pk}": soal_dua.opsi.get(urutan=2).pk,
            },
        )
        self.assertRedirects(response, reverse("daftar_ujian"))
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertEqual(pengumpulan.nilai, Decimal("50.00"))
        self.assertEqual(
            list(JawabanUjianPilihanGanda.objects.filter(pengumpulan=pengumpulan).order_by("soal__urutan").values_list("skor", flat=True)),
            [Decimal("50.00"), Decimal("0.00")],
        )
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, "Lihat Hasil")
        nilai_saya = self.client.get(reverse("daftar_nilai"))
        self.assertContains(nilai_saya, "50,00")
        hasil_siswa = self.client.get(reverse("hasil_ujian", args=[ujian.pk]))
        self.assertContains(hasil_siswa, "Hasil Saya")
        self.assertContains(hasil_siswa, "JAWABAN ANDA")
        self.assertContains(hasil_siswa, "KUNCI JAWABAN")
        self.assertContains(hasil_siswa, "Benar")
        self.assertContains(hasil_siswa, "Salah")
        self.assertContains(hasil_siswa, "Skor 0,00")
        self.assertContains(hasil_siswa, "Merah putih")

        self.client.force_login(self.gadik)
        hasil = self.client.get(reverse("hasil_ujian", args=[ujian.pk]))
        self.assertContains(hasil, "HASIL UJIAN PILIHAN GANDA")
        self.assertContains(hasil, self.serdik.display_name)
        self.assertContains(hasil, "50,00")
        self.assertContains(hasil, "Lihat Hasil")
        self.assertContains(hasil, f"?pengumpulan={pengumpulan.pk}")
        hasil = self.client.get(f'{reverse("hasil_ujian", args=[ujian.pk])}?pengumpulan={pengumpulan.pk}')
        self.assertContains(hasil, "Kembali ke daftar hasil ujian")
        self.assertContains(hasil, f'href="{reverse("hasil_ujian", args=[ujian.pk])}"')
        self.assertContains(hasil, "Merah putih")
        self.assertContains(hasil, "Benar")
        self.assertContains(hasil, "Salah")
        self.assertContains(hasil, "Skor 0,00")

    def test_manual_essay_checking_leaves_score_empty(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Manual",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab soal.",
            waktu_mulai=timezone.now() - timedelta(minutes=5),
            durasi_menit=60,
        )
        soal = SoalUjianEsai.objects.create(
            ujian=ujian,
            urutan=1,
            pertanyaan="Jelaskan keamanan.",
            kunci_jawaban="aman",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.MANUAL,
        )
        self.client.post(reverse("mulai_ujian_esai", args=[ujian.pk]))
        self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {f"soal_{soal.pk}": "aman"},
        )
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertIsNone(pengumpulan.nilai)

        self.client.force_login(self.gadik)
        hasil = self.client.get(reverse("hasil_ujian", args=[ujian.pk]))
        self.assertContains(hasil, self.serdik.display_name)
        self.assertContains(hasil, "Lihat Hasil")
        hasil = self.client.get(f'{reverse("hasil_ujian", args=[ujian.pk])}?pengumpulan={pengumpulan.pk}')
        self.assertContains(hasil, "Kembali ke daftar hasil ujian")
        self.assertContains(hasil, "Jelaskan keamanan.")
        self.assertContains(hasil, "aman")
        response = self.client.post(
            reverse("hasil_ujian", args=[ujian.pk]),
            {
                "pengumpulan": pengumpulan.pk,
                f"skor_{pengumpulan.jawaban_esai.get().pk}": 87.5,
            },
        )
        self.assertRedirects(response, f'{reverse("hasil_ujian", args=[ujian.pk])}?pengumpulan={pengumpulan.pk}')
        pengumpulan.refresh_from_db()
        self.assertEqual(pengumpulan.nilai, 87.5)

    def test_exam_has_explicit_end_time_and_attempt_uses_earliest_limit(self):
        mulai = timezone.now() + timedelta(hours=1)
        selesai = mulai + timedelta(hours=3)
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Terjadwal",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab dengan lengkap.",
            waktu_mulai=mulai,
            waktu_selesai=selesai,
            durasi_menit=75,
        )
        percobaan = PengumpulanUjian.objects.create(
            ujian=ujian,
            serdik=self.serdik,
            started_at=mulai + timedelta(minutes=10),
        )
        self.assertEqual(ujian.waktu_selesai, selesai)
        self.assertEqual(percobaan.batas_waktu, mulai + timedelta(minutes=85))

    def test_student_must_confirm_start_and_expired_attempt_is_locked(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Dengan Timer",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab dengan lengkap.",
            waktu_mulai=timezone.now() - timedelta(hours=2),
            waktu_selesai=timezone.now() + timedelta(hours=2),
            durasi_menit=60,
        )
        SoalUjianEsai.objects.create(
            ujian=ujian,
            urutan=1,
            pertanyaan="Jelaskan keamanan.",
            kunci_jawaban="aman",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.MANUAL,
        )
        self.assertRedirects(
            self.client.get(reverse("kerjakan_ujian_esai", args=[ujian.pk])),
            reverse("daftar_ujian"),
        )
        self.assertFalse(PengumpulanUjian.objects.filter(ujian=ujian, serdik=self.serdik).exists())

        response = self.client.post(reverse("mulai_ujian_esai", args=[ujian.pk]))
        self.assertRedirects(response, reverse("kerjakan_ujian_esai", args=[ujian.pk]))
        percobaan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        self.assertIsNotNone(percobaan.started_at)
        self.assertIsNone(percobaan.submitted_at)
        self.assertContains(self.client.get(reverse("kerjakan_ujian_esai", args=[ujian.pk])), "SISA WAKTU")

        percobaan.started_at = timezone.now() - timedelta(minutes=61)
        percobaan.save(update_fields=["started_at"])
        self.assertRedirects(
            self.client.get(reverse("kerjakan_ujian_esai", args=[ujian.pk])),
            reverse("daftar_ujian"),
        )
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, "Waktu pengerjaan habis")

    def test_exam_owner_can_add_essay_question_and_answer_key(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Esai",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab dengan lengkap.",
            waktu_mulai=timezone.now() + timedelta(hours=1),
            durasi_menit=60,
        )
        self.client.force_login(self.gadik)
        daftar = self.client.get(reverse("daftar_ujian"))
        self.assertContains(daftar, "Input Soal &amp; Kunci Jawaban", html=False)

        response = self.client.post(
            reverse("kelola_soal_esai", args=[ujian.pk]),
            {
                "urutan": 1,
                "pertanyaan": "Jelaskan prinsip keamanan.",
                "kunci_jawaban": "Kerahasiaan, integritas, dan ketersediaan.",
                "pemeriksaan": SoalUjianEsai.Pemeriksaan.PENALARAN,
            },
        )
        self.assertRedirects(response, reverse("kelola_soal_esai", args=[ujian.pk]))
        soal = SoalUjianEsai.objects.get(ujian=ujian)
        self.assertEqual(soal.kunci_jawaban, "Kerahasiaan, integritas, dan ketersediaan.")
        self.assertEqual(soal.pemeriksaan, SoalUjianEsai.Pemeriksaan.PENALARAN)

        self.client.force_login(self.gadik_lain)
        self.assertEqual(self.client.get(reverse("kelola_soal_esai", args=[ujian.pk])).status_code, 404)
        self.client.force_login(self.serdik)
        self.assertEqual(self.client.get(reverse("kelola_soal_esai", args=[ujian.pk])).status_code, 403)

    def test_mixed_question_modes_require_teacher_confirmation(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Campuran",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab semua soal.",
            waktu_mulai=timezone.now() - timedelta(minutes=5),
            durasi_menit=60,
        )
        otomatis = SoalUjianEsai.objects.create(
            ujian=ujian, urutan=1, pertanyaan="Warna bendera?", kunci_jawaban="merah putih",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.OTOMATIS,
        )
        manual = SoalUjianEsai.objects.create(
            ujian=ujian, urutan=2, pertanyaan="Jelaskan disiplin.", kunci_jawaban="disiplin",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.MANUAL,
        )
        penalaran = SoalUjianEsai.objects.create(
            ujian=ujian, urutan=3, pertanyaan="Mengapa keamanan penting?", kunci_jawaban="keamanan mencegah risiko",
            pemeriksaan=SoalUjianEsai.Pemeriksaan.PENALARAN,
        )
        self.client.post(reverse("mulai_ujian_esai", args=[ujian.pk]))
        self.client.post(
            reverse("kerjakan_ujian_esai", args=[ujian.pk]),
            {
                f"soal_{otomatis.pk}": "merah putih",
                f"soal_{manual.pk}": "Disiplin menjaga ketertiban.",
                f"soal_{penalaran.pk}": "Keamanan penting karena mencegah risiko dan dampak buruk.",
            },
        )
        pengumpulan = PengumpulanUjian.objects.get(ujian=ujian, serdik=self.serdik)
        jawaban = {item.soal_id: item for item in pengumpulan.jawaban_esai.all()}
        self.assertIsNone(pengumpulan.nilai)
        self.assertEqual(jawaban[otomatis.pk].skor, Decimal("33.33"))
        self.assertIsNone(jawaban[manual.pk].skor)
        self.assertIsNotNone(jawaban[penalaran.pk].skor)

        self.client.force_login(self.gadik)
        response = self.client.post(
            reverse("hasil_ujian", args=[ujian.pk]),
            {
                "pengumpulan": pengumpulan.pk,
                f"skor_{jawaban[manual.pk].pk}": "30",
                f"skor_{jawaban[penalaran.pk].pk}": "25",
            },
        )
        self.assertRedirects(response, f'{reverse("hasil_ujian", args=[ujian.pk])}?pengumpulan={pengumpulan.pk}')
        pengumpulan.refresh_from_db()
        self.assertEqual(pengumpulan.nilai, Decimal("88.33"))

    def test_each_role_can_edit_own_profile_and_change_password(self):
        for user, identifier in [
            (self.serdik, "NOSIS-PROFIL"),
            (self.gadik, "NRP-GADIK-PROFIL"),
            (self.admin, "NRP-ADMIN-PROFIL"),
        ]:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("profil"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Profil Saya")
                self.assertContains(response, 'class="sidebar-user dropup"')
                self.assertContains(response, "Akun Saya")
                self.assertContains(response, f'href="{reverse("profil")}"', count=1)
                self.assertContains(response, 'data-bs-target="#logoutConfirmModal"', count=1)
                self.assertNotIn("role", response.context["form"].fields)
                self.assertNotIn("is_active", response.context["form"].fields)

                response = self.client.post(
                    reverse("profil"),
                    {
                        "nip_nrp": identifier,
                        "nama_lengkap": f"Profil {user.get_role_display()}",
                        "email": f"{user.role.lower()}@example.com",
                        "tempat_lahir": "Bandung",
                        "tanggal_lahir": "1990-01-02",
                        "asal_pengiriman": "Polda Jawa Barat",
                        "alamat": "Jalan Profil",
                        "password_baru": "SandiProfil-2026",
                        "konfirmasi_password": "SandiProfil-2026",
                    },
                )
                self.assertRedirects(response, reverse("profil"))
                user.refresh_from_db()
                self.assertEqual(user.username, identifier)
                self.assertEqual(user.nama_lengkap, f"Profil {user.get_role_display()}")
                self.assertTrue(user.check_password("SandiProfil-2026"))
                self.assertEqual(self.client.get(reverse("profil")).status_code, 200)

    def test_submission_status_is_derived_from_deadline(self):
        tepat_waktu = PengumpulanTugas.objects.create(
            tugas=self.tugas,
            serdik=self.serdik,
            file_tugas=SimpleUploadedFile("jawaban.pdf", b"isi"),
        )
        self.assertEqual(tepat_waktu.status, PengumpulanTugas.Status.TERKIRIM)

        tugas_terlambat = Tugas.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul_tugas="Tugas Lewat",
            instruksi="Kerjakan.",
            deadline=timezone.now() - timedelta(hours=1),
        )
        terlambat = PengumpulanTugas.objects.create(
            tugas=tugas_terlambat,
            serdik=self.serdik,
            file_tugas=SimpleUploadedFile("terlambat.pdf", b"isi"),
        )
        self.assertEqual(terlambat.status, PengumpulanTugas.Status.TERLAMBAT)

    def test_student_sees_submitted_confirmation(self):
        PengumpulanTugas.objects.create(
            tugas=self.tugas,
            serdik=self.serdik,
            file_tugas=SimpleUploadedFile("jawaban.pdf", b"isi"),
        )

        response = self.client.get(reverse("detail_tugas", args=[self.tugas.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tugas sudah dikumpulkan")

    def test_graded_submission_cannot_be_reuploaded(self):
        pengumpulan = PengumpulanTugas.objects.create(
            tugas=self.tugas,
            serdik=self.serdik,
            file_tugas=SimpleUploadedFile("awal.pdf", b"awal"),
            nilai=88,
        )
        original_name = pengumpulan.file_tugas.name
        response = self.client.post(
            reverse("kumpulkan_tugas", args=[self.tugas.pk]),
            {"file_tugas": SimpleUploadedFile("baru.pdf", b"baru")},
        )
        self.assertRedirects(response, reverse("detail_tugas", args=[self.tugas.pk]))
        pengumpulan.refresh_from_db()
        self.assertEqual(pengumpulan.file_tugas.name, original_name)
        self.assertEqual(pengumpulan.status, PengumpulanTugas.Status.DINILAI)

    def test_only_assignment_teacher_can_grade(self):
        mapel_kolaborator = MataPelajaran.objects.create(
            kurikulum=self.kurikulum,
            kode_mapel="KOL-01",
            nama_mapel="Mapel Kolaborator",
        )
        mapel_kolaborator.gadik_pengajar.add(self.gadik_lain)
        tugas_kolaborator = Tugas.objects.create(
            kelas=self.kelas,
            mapel=mapel_kolaborator,
            gadik=self.gadik_lain,
            judul_tugas="Tugas Mapel Kolaborator",
            instruksi="Kerjakan tugas kolaborator.",
            deadline=timezone.now() + timedelta(days=1),
        )
        belum_mengumpulkan = CustomUser.objects.create_user(
            username="belum-mengumpulkan",
            nip_nrp="NOSIS-BELUM",
            nama_lengkap="Serdik Belum Mengumpulkan",
            role=CustomUser.Role.SERDIK,
        )
        AnggotaKelas.objects.create(kelas=self.kelas, serdik=belum_mengumpulkan)
        pengumpulan = PengumpulanTugas.objects.create(
            tugas=self.tugas,
            serdik=self.serdik,
            file_tugas=SimpleUploadedFile("jawaban.pdf", b"isi"),
        )
        self.client.force_login(self.gadik_lain)
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_response, tugas_kolaborator.judul_tugas)
        self.assertNotContains(dashboard_response, self.tugas.judul_tugas)
        kelas_response = self.client.get(reverse("detail_kelas", args=[self.kelas.pk]))
        self.assertContains(kelas_response, tugas_kolaborator.judul_tugas)
        self.assertNotContains(kelas_response, self.tugas.judul_tugas)
        self.assertEqual(self.client.get(reverse("detail_tugas", args=[self.tugas.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("daftar_pengumpulan", args=[self.tugas.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("nilai_pengumpulan", args=[pengumpulan.pk])).status_code, 403)
        self.mapel.gadik_pengajar.add(self.gadik_lain)
        detail_response = self.client.get(reverse("detail_tugas", args=[self.tugas.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, self.mapel.kode_mapel)
        self.assertNotContains(detail_response, reverse("ubah_tugas", args=[self.tugas.pk]))
        self.assertNotContains(detail_response, reverse("hapus_tugas", args=[self.tugas.pk]))
        daftar_response = self.client.get(reverse("daftar_pengumpulan", args=[self.tugas.pk]))
        self.assertContains(daftar_response, "Lihat Tugas")
        self.assertContains(daftar_response, pengumpulan.file_tugas.url, count=2)
        self.assertContains(daftar_response, 'target="_blank"')
        self.assertContains(daftar_response, "Unduh tugas")
        self.assertContains(daftar_response, belum_mengumpulkan.display_name)
        self.assertContains(daftar_response, 'status-badge status-terkirim')
        self.assertContains(
            daftar_response,
            'bg-secondary-subtle text-secondary-emphasis rounded-pill">Belum Mengumpulkan',
        )
        self.assertLess(
            daftar_response.content.index(self.serdik.display_name.encode()),
            daftar_response.content.index(belum_mengumpulkan.display_name.encode()),
        )

        response = self.client.post(
            reverse("nilai_pengumpulan", args=[pengumpulan.pk]), {"nilai": "91.50", "catatan_gadik": "Baik."}
        )
        self.assertRedirects(response, reverse("daftar_pengumpulan", args=[self.tugas.pk]))
        pengumpulan.refresh_from_db()
        self.assertEqual(str(pengumpulan.nilai), "91.50")
        self.assertEqual(pengumpulan.status, PengumpulanTugas.Status.DINILAI)
        self.assertEqual(pengumpulan.dinilai_oleh, self.gadik_lain)

        self.client.force_login(self.serdik)
        nilai_response = self.client.get(reverse("daftar_nilai"))
        self.assertContains(nilai_response, "Gadik Penilai")
        self.assertContains(nilai_response, self.gadik_lain.display_name)
        detail_response = self.client.get(reverse("detail_tugas", args=[self.tugas.pk]))
        self.assertContains(detail_response, f"Dinilai oleh {self.gadik_lain.display_name}")

    def test_only_owner_teacher_can_edit_assignment(self):
        self.client.force_login(self.gadik_lain)
        self.assertEqual(self.client.get(reverse("ubah_tugas", args=[self.tugas.pk])).status_code, 404)
        self.client.force_login(self.gadik)
        self.assertEqual(self.client.get(reverse("ubah_tugas", args=[self.tugas.pk])).status_code, 200)

    def test_student_grade_page_shows_own_assignment_and_exam_tables(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Kompetensi",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab seluruh soal.",
            waktu_mulai=timezone.now() - timedelta(hours=1),
            durasi_menit=60,
        )
        PengumpulanUjian.objects.create(
            ujian=ujian, serdik=self.serdik, started_at=timezone.now(), submitted_at=timezone.now(), nilai="88.50"
        )
        ujian_lain = Ujian.objects.create(
            kelas=self.kelas_lain,
            mapel=self.mapel_lain,
            gadik=self.gadik_lain,
            judul="Ujian Siswa Lain",
            metode=Ujian.Metode.ESAI,
            instruksi="Jawab seluruh soal.",
            waktu_mulai=timezone.now() - timedelta(hours=1),
            durasi_menit=60,
        )
        PengumpulanUjian.objects.create(
            ujian=ujian_lain,
            serdik=self.serdik_lain,
            started_at=timezone.now(),
            submitted_at=timezone.now(),
            nilai="95.00",
        )

        response = self.client.get(reverse("daftar_nilai"))

        self.assertContains(response, "Nilai Tugas")
        self.assertContains(response, "Nilai Ujian")
        self.assertContains(response, ujian.judul)
        self.assertContains(response, "88,50")
        self.assertNotContains(response, ujian_lain.judul)

    def test_assignment_form_rejects_subject_from_another_curriculum(self):
        form = TugasForm(
            data={
                "kelas": self.kelas.pk,
                "mapel": self.mapel_lain.pk,
                "judul_tugas": "Tidak Valid",
                "instruksi": "Instruksi",
                "deadline": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "bobot": 100,
            },
            gadik=self.gadik,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("mapel", form.errors)

    def test_teacher_sees_teaching_classes_students_and_only_assigned_subjects(self):
        self.client.force_login(self.gadik)
        response = self.client.get(reverse("daftar_kelas"))
        self.assertContains(response, self.kelas.nama_kelas)
        self.assertContains(response, self.kelas_lain.nama_kelas)
        self.assertContains(response, 'class="class-card class-card-large"', count=2)
        self.assertNotContains(response, self.serdik.display_name)

        detail_response = self.client.get(reverse("detail_kelas", args=[self.kelas.pk]))
        self.assertContains(detail_response, self.mapel.nama_mapel)
        self.assertContains(detail_response, "Tambah modul")
        self.assertContains(detail_response, "Buat tugas")
        self.assertContains(detail_response, f'{reverse("buat_tugas")}?kelas={self.kelas.pk}')
        self.assertContains(detail_response, "Daftar Siswa")
        self.assertContains(detail_response, self.serdik.display_name)
        self.assertLess(
            detail_response.content.index(b"Penugasan"),
            detail_response.content.index(b"Daftar Siswa"),
        )

        form_response = self.client.get(reverse("buat_tugas"))
        form = form_response.context["form"]
        self.assertSetEqual(
            set(form.fields["kelas"].queryset.values_list("pk", flat=True)),
            {self.kelas.pk, self.kelas_lain.pk},
        )
        self.assertSetEqual(
            set(form.fields["mapel"].queryset.values_list("pk", flat=True)),
            {self.mapel.pk},
        )

        contextual_form = self.client.get(
            reverse("buat_tugas"), {"kelas": self.kelas.pk}
        ).context["form"]
        self.assertEqual(contextual_form.initial["kelas"], self.kelas)
        self.assertSetEqual(
            set(contextual_form.fields["mapel"].queryset.values_list("pk", flat=True)),
            {self.mapel.pk},
        )

        module_form = self.client.get(reverse("buat_modul")).context["form"]
        self.assertNotIn("kelas", module_form.fields)
        self.assertSetEqual(
            set(module_form.fields["mapel"].queryset.values_list("pk", flat=True)),
            {self.mapel.pk},
        )

        kelas_mapel_lain = Kelas.objects.create(
            nama_kelas="Kelas Mapel Lain",
            kurikulum=self.kurikulum_lain,
            gadik_pembina=self.gadik_lain,
        )
        modul_mapel_lain = ModulBelajar.objects.create(
            kelas=kelas_mapel_lain,
            mapel=self.mapel_lain,
            gadik=self.gadik_lain,
            judul="Modul Etika Umum",
            deskripsi="Modul dari mata pelajaran Gadik lain.",
            file_modul=SimpleUploadedFile("etika.pdf", b"materi", content_type="application/pdf"),
        )
        katalog_modul = self.client.get(reverse("daftar_modul"))
        self.assertContains(katalog_modul, "Modul")
        self.assertContains(katalog_modul, "Tambah Modul")
        self.assertContains(katalog_modul, self.mapel_lain.nama_mapel)
        self.assertContains(katalog_modul, modul_mapel_lain.judul)
        self.assertContains(katalog_modul, modul_mapel_lain.file_modul.url, count=2)

        modul_tidak_diizinkan = self.client.post(
            reverse("buat_modul"),
            {
                "mapel": self.mapel_lain.pk,
                "judul": "Modul Tidak Diizinkan",
                "deskripsi": "Tidak boleh diterbitkan oleh Gadik ini.",
                "file_modul": SimpleUploadedFile(
                    "ditolak.pdf", b"materi", content_type="application/pdf"
                ),
            },
        )
        self.assertEqual(modul_tidak_diizinkan.status_code, 200)
        self.assertFalse(ModulBelajar.objects.filter(judul="Modul Tidak Diizinkan").exists())

        module_response = self.client.post(
            reverse("buat_modul"),
            {
                "mapel": self.mapel.pk,
                "judul": "Modul Gadik Bersama",
                "deskripsi": "Materi untuk seluruh kelas.",
                "file_modul": SimpleUploadedFile(
                    "modul-gadik.pdf", b"materi", content_type="application/pdf"
                ),
            },
        )
        self.assertRedirects(module_response, reverse("daftar_modul"))
        modul_gadik = ModulBelajar.objects.filter(judul="Modul Gadik Bersama")
        self.assertEqual(modul_gadik.count(), 2)
        self.assertSetEqual(
            set(modul_gadik.values_list("kelas_id", flat=True)),
            {self.kelas.pk, self.kelas_lain.pk},
        )
        self.assertEqual(modul_gadik.values_list("file_modul", flat=True).distinct().count(), 1)
        self.assertFalse(modul_gadik.exclude(gadik=self.gadik).exists())
        katalog_setelah_upload = self.client.get(reverse("daftar_modul"))
        self.assertEqual(len(katalog_setelah_upload.context["modul_per_mapel"]), 2)
        self.assertContains(
            katalog_setelah_upload,
            f'data-mapel-id="{self.mapel.pk}"',
            count=1,
        )
        kelompok_modul_gadik = next(
            kelompok
            for kelompok in katalog_setelah_upload.context["modul_per_mapel"]
            if kelompok["mapel"].pk == self.mapel.pk
        )
        self.assertEqual(len(kelompok_modul_gadik["modul"]), 1)

        response = self.client.post(
            reverse("buat_tugas"),
            {
                "kelas": self.kelas_lain.pk,
                "mapel": self.mapel.pk,
                "judul_tugas": "Tugas Kelas B",
                "instruksi": "Kerjakan untuk kelas B.",
                "deadline": (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                "bobot": 100,
            },
        )
        tugas = Tugas.objects.get(judul_tugas="Tugas Kelas B")
        self.assertRedirects(response, reverse("detail_tugas", args=[tugas.pk]))
        self.assertEqual(tugas.gadik, self.gadik)
        self.assertEqual(tugas.kelas, self.kelas_lain)

    def test_admin_management_pages_are_admin_only(self):
        self.assertEqual(self.client.get(reverse("pengelolaan_admin")).status_code, 403)
        self.client.force_login(self.admin)
        for url_name in [
            "pengelolaan_admin",
            "daftar_kurikulum",
            "tambah_kurikulum",
            "tambah_kelas",
            "daftar_mata_pelajaran",
            "tambah_mata_pelajaran",
            "daftar_gadik",
            "tambah_gadik",
            "tambah_modul_admin",
        ]:
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_admin_can_create_curriculum(self):
        self.client.force_login(self.admin)
        daftar_response = self.client.get(reverse("daftar_kurikulum"))
        kurikulum_context = next(
            item for item in daftar_response.context["kurikulum"] if item.pk == self.kurikulum.pk
        )
        self.assertEqual(kurikulum_context.jumlah_siswa, 2)

        response = self.client.post(
            reverse("tambah_kurikulum"),
            {"nama_kurikulum": "Kurikulum Baru", "tahun_ajaran": "2027/2028", "is_active": "on"},
        )
        self.assertRedirects(response, reverse("daftar_kurikulum"))
        kurikulum = Kurikulum.objects.get(nama_kurikulum="Kurikulum Baru")
        self.assertTrue(kurikulum.is_active)

        response = self.client.post(reverse("ubah_status_kurikulum", args=[kurikulum.pk]))
        self.assertRedirects(response, reverse("daftar_kurikulum"))
        kurikulum.refresh_from_db()
        self.assertFalse(kurikulum.is_active)

        response = self.client.post(
            reverse("ubah_status_kurikulum", args=[kurikulum.pk]),
            {"is_active": "on"},
        )
        self.assertRedirects(response, reverse("daftar_kurikulum"))
        kurikulum.refresh_from_db()
        self.assertTrue(kurikulum.is_active)

    def test_admin_can_create_gadik_with_hashed_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("tambah_gadik"),
            {
                "nama_lengkap": "Gadik Baru",
                "nip_nrp": "NRP-9001",
                "email": "gadik.baru@example.com",
                "password1": "SandiAman-9001",
                "password2": "SandiAman-9001",
            },
        )
        self.assertRedirects(response, reverse("pengelolaan_admin"))
        gadik = CustomUser.objects.get(nip_nrp="NRP-9001")
        self.assertEqual(gadik.username, "NRP-9001")
        self.assertEqual(gadik.role, CustomUser.Role.GADIK)
        self.assertTrue(gadik.check_password("SandiAman-9001"))

    def test_admin_can_create_student_profile(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("tambah_siswa"),
            {
                "nip_nrp": "NOSIS-9001",
                "nama_lengkap": "Siswa Baru",
                "tempat_lahir": "Bandung",
                "tanggal_lahir": "2005-08-17",
                "asal_pengiriman": "Polda Jawa Barat",
                "alamat": "Jalan Presisi 1",
                "password1": "SandiAman-9001",
                "password2": "SandiAman-9001",
            },
        )
        self.assertRedirects(response, reverse("daftar_siswa"))
        siswa = CustomUser.objects.get(nip_nrp="NOSIS-9001")
        self.assertEqual(siswa.role, CustomUser.Role.SERDIK)
        self.assertEqual(siswa.tempat_lahir, "Bandung")
        self.assertEqual(siswa.asal_pengiriman, "Polda Jawa Barat")

    def test_admin_can_edit_student_and_change_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("ubah_siswa", args=[self.serdik.pk]),
            {
                "nip_nrp": "NOSIS-EDIT-01",
                "nama_lengkap": "Siswa Diperbarui",
                "tempat_lahir": "Bogor",
                "tanggal_lahir": "2004-01-02",
                "asal_pengiriman": "Polda Jawa Barat",
                "alamat": "Jalan Baru",
                "is_active": "on",
                "password_baru": "SandiBaru-Serdik-2026",
                "konfirmasi_password": "SandiBaru-Serdik-2026",
            },
        )
        self.assertRedirects(response, reverse("daftar_siswa"))
        self.serdik.refresh_from_db()
        self.assertEqual(self.serdik.username, "NOSIS-EDIT-01")
        self.assertEqual(self.serdik.nama_lengkap, "Siswa Diperbarui")
        self.assertTrue(self.serdik.check_password("SandiBaru-Serdik-2026"))
        self.assertContains(
            self.client.get(reverse("daftar_siswa")),
            reverse("ubah_siswa", args=[self.serdik.pk]),
        )

    def test_admin_can_edit_teacher_and_change_password(self):
        self.client.force_login(self.admin)
        edit_response = self.client.get(reverse("ubah_gadik", args=[self.gadik.pk]))
        mapel_field = edit_response.context["form"].fields["mata_pelajaran_diajar"]
        self.assertIn(self.mapel, mapel_field.initial)
        self.assertSetEqual(
            set(mapel_field.queryset.values_list("pk", flat=True)),
            {self.mapel.pk, self.mapel_lain.pk},
        )

        response = self.client.post(
            reverse("ubah_gadik", args=[self.gadik.pk]),
            {
                "nip_nrp": "NRP-GADIK-EDIT",
                "nama_lengkap": "Gadik Diperbarui",
                "email": "gadik.edit@example.com",
                "is_active": "on",
                "password_baru": "SandiBaru-Gadik-2026",
                "konfirmasi_password": "SandiBaru-Gadik-2026",
                "mata_pelajaran_diajar": [self.mapel_lain.pk],
            },
        )
        self.assertRedirects(response, reverse("daftar_gadik"))
        self.gadik.refresh_from_db()
        self.assertEqual(self.gadik.username, "NRP-GADIK-EDIT")
        self.assertEqual(self.gadik.email, "gadik.edit@example.com")
        self.assertTrue(self.gadik.check_password("SandiBaru-Gadik-2026"))
        self.assertSetEqual(
            set(self.gadik.mata_pelajaran_diampu.values_list("pk", flat=True)),
            {self.mapel_lain.pk},
        )
        self.assertIn(self.gadik_lain, self.mapel_lain.gadik_pengajar.all())

        response = self.client.post(
            reverse("ubah_gadik", args=[self.gadik.pk]),
            {
                "nip_nrp": "NRP-GADIK-EDIT",
                "nama_lengkap": "Gadik Diperbarui Lagi",
                "email": "gadik.edit@example.com",
                "is_active": "on",
                "password_baru": "",
                "konfirmasi_password": "",
                "mata_pelajaran_diajar": [self.mapel_lain.pk],
            },
        )
        self.assertRedirects(response, reverse("daftar_gadik"))
        self.gadik.refresh_from_db()
        self.assertTrue(self.gadik.check_password("SandiBaru-Gadik-2026"))
        self.assertContains(
            self.client.get(reverse("daftar_gadik")),
            reverse("ubah_gadik", args=[self.gadik.pk]),
        )

    def test_admin_can_manage_multiple_students_in_one_class(self):
        siswa_baru = CustomUser.objects.create_user(
            username="siswa-baru",
            nip_nrp="NOSIS-02",
            nama_lengkap="Bambang Siswa",
            role=CustomUser.Role.SERDIK,
        )
        siswa_baru_lain = CustomUser.objects.create_user(
            username="siswa-baru-lain",
            nip_nrp="NOSIS-03",
            nama_lengkap="Citra Siswa",
            role=CustomUser.Role.SERDIK,
        )
        self.client.force_login(self.admin)
        url = reverse("kelola_anggota_kelas", args=[self.kelas.pk])

        form_response = self.client.get(url)
        pilihan = form_response.context["form"].fields["siswa"].queryset
        self.assertNotIn(self.serdik, pilihan)
        self.assertIn(siswa_baru, pilihan)
        self.assertContains(form_response, 'type="checkbox"', count=2)
        self.assertContains(form_response, 'id="student-picker-search"')
        self.assertContains(form_response, "Cari NOSIS atau nama siswa")

        response = self.client.post(url, {"siswa": [siswa_baru.pk, siswa_baru_lain.pk]})
        self.assertRedirects(response, url)
        self.assertEqual(
            AnggotaKelas.objects.filter(kelas=self.kelas, serdik__in=[siswa_baru, siswa_baru_lain]).count(),
            2,
        )

        other_class_response = self.client.get(reverse("kelola_anggota_kelas", args=[self.kelas_lain.pk]))
        other_choices = other_class_response.context["form"].fields["siswa"].queryset
        self.assertNotIn(siswa_baru, other_choices)
        self.assertNotIn(siswa_baru_lain, other_choices)

        search_response = self.client.get(url, {"q": "Bambang"})
        self.assertContains(search_response, "Bambang Siswa")
        self.assertNotContains(search_response, "Citra Siswa")

        anggota = AnggotaKelas.objects.get(kelas=self.kelas, serdik=siswa_baru)
        response = self.client.post(reverse("hapus_anggota_kelas", args=[self.kelas.pk, anggota.pk]))
        self.assertRedirects(response, url)
        self.assertFalse(AnggotaKelas.objects.filter(pk=anggota.pk).exists())
        available_again = self.client.get(reverse("kelola_anggota_kelas", args=[self.kelas_lain.pk]))
        self.assertIn(siswa_baru, available_again.context["form"].fields["siswa"].queryset)

    def test_admin_can_assign_multiple_teachers_to_subject(self):
        self.client.force_login(self.admin)
        form_response = self.client.get(reverse("tambah_mata_pelajaran"))
        self.assertContains(form_response, 'type="checkbox"', count=2)
        response = self.client.post(
            reverse("tambah_mata_pelajaran"),
            {
                "kurikulum": self.kurikulum.pk,
                "kode_mapel": "KOM-02",
                "nama_mapel": "Komunikasi Kepolisian",
                "gadik_pengajar": [self.gadik.pk, self.gadik_lain.pk],
            },
        )
        self.assertRedirects(response, reverse("daftar_mata_pelajaran"))
        mapel = MataPelajaran.objects.get(kode_mapel="KOM-02")
        self.assertSetEqual(set(mapel.gadik_pengajar.values_list("id", flat=True)), {self.gadik.id, self.gadik_lain.id})

        daftar_response = self.client.get(reverse("daftar_mata_pelajaran"))
        module_url = f'{reverse("tambah_modul_admin")}?mapel={mapel.pk}'
        self.assertContains(daftar_response, module_url)

        module_response = self.client.get(module_url)
        module_form = module_response.context["form"]
        self.assertTrue(module_form.fields["kurikulum"].disabled)
        self.assertTrue(module_form.fields["mapel"].disabled)
        self.assertNotIn("gadik", module_form.fields)

    def test_admin_can_search_subject_by_name(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("daftar_mata_pelajaran"), {"q": "aman"})
        self.assertContains(response, self.mapel.nama_mapel)
        self.assertNotContains(response, self.mapel_lain.nama_mapel)
        self.assertEqual(response.context["pencarian"], "aman")

        empty_response = self.client.get(reverse("daftar_mata_pelajaran"), {"q": "tidak ditemukan"})
        self.assertContains(empty_response, "Mata pelajaran tidak ditemukan")

    def test_admin_module_is_published_to_every_class_in_curriculum(self):
        kelas_kurikulum_lain = Kelas.objects.create(
            nama_kelas="Kelas Kurikulum Lain",
            kurikulum=self.kurikulum_lain,
            gadik_pembina=self.gadik,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            f'{reverse("tambah_modul_admin")}?mapel={self.mapel.pk}',
            {
                "kurikulum": self.kurikulum.pk,
                "mapel": self.mapel.pk,
                "judul": "Modul Bersama",
                "deskripsi": "Materi untuk seluruh kelas.",
                "file_modul": SimpleUploadedFile("modul.pdf", b"materi", content_type="application/pdf"),
            },
        )
        self.assertRedirects(response, reverse("pengelolaan_admin"))
        modul = ModulBelajar.objects.filter(judul="Modul Bersama")
        self.assertEqual(modul.count(), 2)
        self.assertSetEqual(set(modul.values_list("kelas_id", flat=True)), {self.kelas.id, self.kelas_lain.id})
        self.assertFalse(modul.filter(kelas=kelas_kurikulum_lain).exists())
        self.assertEqual(modul.values_list("file_modul", flat=True).distinct().count(), 1)
        self.assertFalse(modul.exclude(gadik=self.gadik).exists())

        daftar_response = self.client.get(reverse("daftar_mata_pelajaran"))
        mapel_context = next(item for item in daftar_response.context["mapel"] if item.pk == self.mapel.pk)
        self.assertEqual(len(mapel_context.modul_tersedia), 1)
        self.assertContains(daftar_response, "Modul Bersama")
        self.assertContains(daftar_response, "Buka Modul", count=1)
        self.assertContains(daftar_response, modul.first().file_modul.url, count=1)

        pengelolaan_response = self.client.get(reverse("pengelolaan_admin"))
        self.assertEqual(len(pengelolaan_response.context["modul"]), 1)
        self.assertEqual(pengelolaan_response.context["modul"][0].judul, "Modul Bersama")

    def test_daftar_ujian_separates_active_and_completed_exams(self):
        self.client.force_login(self.gadik)
        ujian_aktif = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Aktif Berlangsung",
            metode=Ujian.Metode.PILIHAN_GANDA,
            instruksi="Kerjakan dengan teliti.",
            waktu_mulai=timezone.now() - timedelta(minutes=10),
            waktu_selesai=timezone.now() + timedelta(minutes=50),
            durasi_menit=60,
        )
        ujian_selesai = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Riwayat Selesai",
            metode=Ujian.Metode.ESAI,
            instruksi="Ujian kemarin.",
            waktu_mulai=timezone.now() - timedelta(hours=3),
            waktu_selesai=timezone.now() - timedelta(hours=1),
            durasi_menit=60,
        )

        response = self.client.get(reverse("daftar_ujian"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("ujian_aktif", response.context)
        self.assertIn("ujian_selesai", response.context)
        aktif_ids = [item.pk for item in response.context["ujian_aktif"]]
        selesai_ids = [item.pk for item in response.context["ujian_selesai"]]
        self.assertIn(ujian_aktif.pk, aktif_ids)
        self.assertNotIn(ujian_selesai.pk, aktif_ids)
        self.assertIn(ujian_selesai.pk, selesai_ids)
        self.assertNotIn(ujian_aktif.pk, selesai_ids)

        self.assertContains(response, "Ujian Sedang Berlangsung &amp; Akan Datang")
        self.assertContains(response, "Ujian yang Sudah Selesai Dilaksanakan")
        self.assertContains(response, "Ujian Aktif Berlangsung")
        self.assertContains(response, "Ujian Riwayat Selesai")
        self.assertContains(response, reverse("export_hasil_ujian_excel", args=[ujian_aktif.pk]))
        self.assertContains(response, reverse("export_hasil_ujian_pdf", args=[ujian_aktif.pk]))

    def test_gadik_can_export_exam_results_excel_and_pdf(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Penilaian Akhir",
            metode=Ujian.Metode.PILIHAN_GANDA,
            instruksi="Pilihlah opsi yang benar.",
            waktu_mulai=timezone.now() - timedelta(hours=2),
            waktu_selesai=timezone.now() - timedelta(hours=1),
            durasi_menit=60,
        )
        soal = SoalUjianPilihanGanda.objects.create(
            ujian=ujian, urutan=1, pertanyaan="Apa itu integritas?"
        )
        opsi_benar = OpsiUjianPilihanGanda.objects.create(
            soal=soal, urutan=1, teks="Kejujuran dan konsistensi", is_kunci=True
        )
        pengumpulan = PengumpulanUjian.objects.create(
            ujian=ujian,
            serdik=self.serdik,
            started_at=timezone.now() - timedelta(hours=2),
            submitted_at=timezone.now() - timedelta(hours=1, minutes=30),
            nilai=Decimal("100.00"),
        )
        JawabanUjianPilihanGanda.objects.create(
            pengumpulan=pengumpulan,
            soal=soal,
            opsi=opsi_benar,
            skor=Decimal("100.00"),
        )

        self.client.force_login(self.gadik)

        # 1. Export Excel
        res_excel = self.client.get(reverse("export_hasil_ujian_excel", args=[ujian.pk]))
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(
            res_excel["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("Hasil_Ujian_", res_excel["Content-Disposition"])
        self.assertTrue(res_excel.content.startswith(b"PK"))

        # 2. Export PDF
        res_pdf = self.client.get(reverse("export_hasil_ujian_pdf", args=[ujian.pk]))
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf["Content-Type"], "application/pdf")
        self.assertIn("Hasil_Ujian_", res_pdf["Content-Disposition"])
        self.assertTrue(res_pdf.content.startswith(b"%PDF"))

        # 3. Check export buttons exist on hasil_ujian page for Gadik
        hasil_page = self.client.get(reverse("hasil_ujian", args=[ujian.pk]))
        self.assertContains(hasil_page, reverse("export_hasil_ujian_excel", args=[ujian.pk]))
        self.assertContains(hasil_page, reverse("export_hasil_ujian_pdf", args=[ujian.pk]))

    def test_student_and_unauthorized_gadik_cannot_export(self):
        ujian = Ujian.objects.create(
            kelas=self.kelas,
            mapel=self.mapel,
            gadik=self.gadik,
            judul="Ujian Rahasia",
            metode=Ujian.Metode.ESAI,
            instruksi="Esai rahasia.",
            waktu_mulai=timezone.now() - timedelta(hours=1),
            waktu_selesai=timezone.now() + timedelta(hours=1),
            durasi_menit=60,
        )

        # Serdik should be forbidden (403)
        self.client.force_login(self.serdik)
        res_excel_serdik = self.client.get(reverse("export_hasil_ujian_excel", args=[ujian.pk]))
        self.assertEqual(res_excel_serdik.status_code, 403)
        res_pdf_serdik = self.client.get(reverse("export_hasil_ujian_pdf", args=[ujian.pk]))
        self.assertEqual(res_pdf_serdik.status_code, 403)

        # Gadik lain (not teaching this mapel) should get 404
        self.client.force_login(self.gadik_lain)
        res_excel_gadik_lain = self.client.get(reverse("export_hasil_ujian_excel", args=[ujian.pk]))
        self.assertEqual(res_excel_gadik_lain.status_code, 404)
        res_pdf_gadik_lain = self.client.get(reverse("export_hasil_ujian_pdf", args=[ujian.pk]))
        self.assertEqual(res_pdf_gadik_lain.status_code, 404)

