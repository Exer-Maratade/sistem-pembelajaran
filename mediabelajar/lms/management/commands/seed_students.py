import os
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from lms.models import CustomUser


class Command(BaseCommand):
    help = "Membuat atau memperbarui 50 data siswa contoh."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.environ.get("LMS_SEED_PASSWORD", "123!"),
            help="Kata sandi untuk seluruh akun siswa seed.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        randomizer = random.Random(2026)
        nama_depan = [
            "Ahmad", "Andi", "Bagus", "Bayu", "Cahya", "Dimas", "Fajar", "Farhan", "Galih", "Hendra",
            "Ilham", "Joko", "Kevin", "Muhammad", "Rangga", "Reza", "Rizky", "Surya", "Teguh", "Yudha",
        ]
        nama_belakang = [
            "Aditya", "Firmansyah", "Gunawan", "Hidayat", "Kurniawan", "Maulana", "Nugraha", "Permana",
            "Prakoso", "Pratama", "Putra", "Ramadhan", "Saputra", "Setiawan", "Wijaya",
        ]
        lokasi = [
            ("Jakarta", "Polda Metro Jaya"),
            ("Bandung", "Polda Jawa Barat"),
            ("Semarang", "Polda Jawa Tengah"),
            ("Surabaya", "Polda Jawa Timur"),
            ("Yogyakarta", "Polda DI Yogyakarta"),
            ("Medan", "Polda Sumatera Utara"),
            ("Palembang", "Polda Sumatera Selatan"),
            ("Makassar", "Polda Sulawesi Selatan"),
            ("Denpasar", "Polda Bali"),
            ("Balikpapan", "Polda Kalimantan Timur"),
        ]
        kombinasi_nama = [(depan, belakang) for depan in nama_depan for belakang in nama_belakang]
        randomizer.shuffle(kombinasi_nama)
        tanggal_awal = date(2001, 1, 1)
        rentang_hari = (date(2007, 12, 31) - tanggal_awal).days

        dibuat = 0
        diperbarui = 0
        for nomor, (depan, belakang) in enumerate(kombinasi_nama[:50], start=1):
            kota, asal = lokasi[(nomor - 1) % len(lokasi)]
            nosis = f"S-2026-{nomor:04d}"
            siswa, created = CustomUser.objects.update_or_create(
                nip_nrp=nosis,
                defaults={
                    "username": f"siswa-{nomor:04d}",
                    "nama_lengkap": f"{depan} {belakang}",
                    "tempat_lahir": kota,
                    "tanggal_lahir": tanggal_awal + timedelta(days=randomizer.randint(0, rentang_hari)),
                    "asal_pengiriman": asal,
                    "alamat": f"Jl. Pendidikan No. {nomor}, {kota}",
                    "email": "",
                    "role": CustomUser.Role.SERDIK,
                    "is_active": True,
                    "is_staff": False,
                    "is_superuser": False,
                },
            )
            siswa.set_password(options["password"])
            siswa.save(update_fields=["password"])
            dibuat += int(created)
            diperbarui += int(not created)

        self.stdout.write(
            self.style.SUCCESS(f"Seeder siswa selesai: {dibuat} dibuat, {diperbarui} diperbarui.")
        )
