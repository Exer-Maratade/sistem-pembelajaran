import os

from django.core.management.base import BaseCommand
from django.db import transaction

from lms.models import CustomUser


class Command(BaseCommand):
    help = "Membuat atau memperbarui pengguna awal untuk role Admin, Gadik, dan Serdik."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.environ.get("LMS_SEED_PASSWORD", "123!"),
            help="Kata sandi untuk seluruh akun seed (default: LMS_SEED_PASSWORD).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        users = [
            {
                "username": "admin",
                "nama_lengkap": "Administrator LMS",
                "nip_nrp": "0001",
                "email": "admin@lmspresisi.local",
                "role": CustomUser.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "username": "gadik1",
                "nama_lengkap": "AKBP Budi Santoso",
                "nip_nrp": "001",
                "email": "  ",
                "role": CustomUser.Role.GADIK,
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "serdik",
                "nama_lengkap": "Andi Pratama",
                "nip_nrp": "SERDIK-001",
                "email": "serdik@lmspresisi.local",
                "role": CustomUser.Role.SERDIK,
                "is_staff": False,
                "is_superuser": False,
            },
        ]

        created_count = 0
        updated_count = 0
        for user_data in users:
            username = user_data.pop("username")
            user, created = CustomUser.objects.update_or_create(username=username, defaults=user_data)
            user.set_password(password)
            user.is_active = True
            # user.save(update_fields=["password", "is_active"])
            user.save()
            created_count += int(created)
            updated_count += int(not created)
            action = "dibuat" if created else "diperbarui"
            self.stdout.write(self.style.SUCCESS(f"{username} ({user.get_role_display()}) {action}."))

        self.stdout.write(
            self.style.SUCCESS(f"Seeder selesai: {created_count} pengguna dibuat, {updated_count} diperbarui.")
        )