from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AnggotaKelas, CustomUser, JawabanUjianEsai, JawabanUjianPilihanGanda, Kelas, Kurikulum, MataPelajaran, ModulBelajar, OpsiUjianPilihanGanda, PengumpulanTugas, PengumpulanUjian, SoalUjianEsai, SoalUjianPilihanGanda, Tugas, Ujian


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "nama_lengkap", "nip_nrp", "role", "is_active"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["username", "nama_lengkap", "nip_nrp", "email"]
    fieldsets = UserAdmin.fieldsets + (("Profil LMS", {"fields": ("nama_lengkap", "nip_nrp", "tempat_lahir", "tanggal_lahir", "asal_pengiriman", "alamat", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profil LMS", {"fields": ("nama_lengkap", "nip_nrp", "tempat_lahir", "tanggal_lahir", "asal_pengiriman", "alamat", "email", "role")}),
    )


class AnggotaKelasInline(admin.TabularInline):
    model = AnggotaKelas
    extra = 1


@admin.register(Kelas)
class KelasAdmin(admin.ModelAdmin):
    list_display = ["nama_kelas", "kurikulum", "gadik_pembina"]
    list_filter = ["kurikulum"]
    search_fields = ["nama_kelas"]
    inlines = [AnggotaKelasInline]


@admin.register(Kurikulum)
class KurikulumAdmin(admin.ModelAdmin):
    list_display = ["nama_kurikulum", "tahun_ajaran", "is_active"]
    list_filter = ["is_active", "tahun_ajaran"]


@admin.register(MataPelajaran)
class MataPelajaranAdmin(admin.ModelAdmin):
    list_display = ["kode_mapel", "nama_mapel", "kurikulum", "daftar_gadik"]
    list_filter = ["kurikulum"]
    search_fields = ["kode_mapel", "nama_mapel"]
    filter_horizontal = ["gadik_pengajar"]

    @admin.display(description="Gadik pengajar")
    def daftar_gadik(self, obj):
        return ", ".join(gadik.display_name for gadik in obj.gadik_pengajar.all()) or "-"


@admin.register(ModulBelajar)
class ModulBelajarAdmin(admin.ModelAdmin):
    list_display = ["judul", "kelas", "mapel", "gadik", "created_at"]
    list_filter = ["kelas", "mapel"]


@admin.register(Tugas)
class TugasAdmin(admin.ModelAdmin):
    list_display = ["judul_tugas", "kelas", "mapel", "gadik", "deadline", "bobot"]
    list_filter = ["kelas", "mapel"]


@admin.register(Ujian)
class UjianAdmin(admin.ModelAdmin):
    list_display = ["judul", "metode", "kelas", "mapel", "gadik", "waktu_mulai", "waktu_selesai", "durasi_menit"]
    list_filter = ["metode", "kelas", "mapel"]


@admin.register(SoalUjianEsai)
class SoalUjianEsaiAdmin(admin.ModelAdmin):
    list_display = ["ujian", "urutan", "pemeriksaan"]
    list_filter = ["pemeriksaan", "ujian__kelas", "ujian__mapel"]


class OpsiUjianPilihanGandaInline(admin.TabularInline):
    model = OpsiUjianPilihanGanda
    extra = 4


@admin.register(SoalUjianPilihanGanda)
class SoalUjianPilihanGandaAdmin(admin.ModelAdmin):
    list_display = ["ujian", "urutan"]
    list_filter = ["ujian__kelas", "ujian__mapel"]
    inlines = [OpsiUjianPilihanGandaInline]


@admin.register(PengumpulanUjian)
class PengumpulanUjianAdmin(admin.ModelAdmin):
    list_display = ["ujian", "serdik", "started_at", "submitted_at", "nilai"]
    list_filter = ["ujian__kelas"]


@admin.register(JawabanUjianEsai)
class JawabanUjianEsaiAdmin(admin.ModelAdmin):
    list_display = ["pengumpulan", "soal", "skor"]


@admin.register(JawabanUjianPilihanGanda)
class JawabanUjianPilihanGandaAdmin(admin.ModelAdmin):
    list_display = ["pengumpulan", "soal", "opsi", "skor"]


@admin.register(PengumpulanTugas)
class PengumpulanTugasAdmin(admin.ModelAdmin):
    list_display = ["tugas", "serdik", "submitted_at", "status", "nilai", "dinilai_oleh"]
    list_filter = ["status", "tugas__kelas"]
    readonly_fields = ["submitted_at", "status"]
