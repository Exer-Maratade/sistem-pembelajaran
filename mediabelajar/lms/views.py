from functools import wraps
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .exports import generate_exam_excel, generate_exam_pdf

from .forms import (
    AdminModulBelajarForm,
    EditGadikForm,
    EditSiswaForm,
    GadikForm,
    JawabanUjianEsaiForm,
    JawabanUjianPilihanGandaForm,
    KelasForm,
    KurikulumForm,
    MataPelajaranForm,
    ModulBelajarForm,
    PenilaianForm,
    PenilaianUjianEsaiForm,
    PengumpulanTugasForm,
    ProfilForm,
    SiswaForm,
    SoalUjianEsaiForm,
    SoalUjianPilihanGandaForm,
    TambahAnggotaKelasForm,
    TugasForm,
    UjianForm,
)
from .models import AnggotaKelas, CustomUser, JawabanUjianEsai, JawabanUjianPilihanGanda, Kelas, Kurikulum, MataPelajaran, ModulBelajar, PengumpulanTugas, PengumpulanUjian, SoalUjianEsai, SoalUjianPilihanGanda, Tugas, Ujian




def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles and not request.user.is_superuser:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def is_admin(user):
    return user.is_superuser or user.role == CustomUser.Role.ADMIN


def ujian_for_manager(user, queryset=None):
    if queryset is None:
        queryset = Ujian.objects.all()
    if is_admin(user):
        return queryset
    return queryset.filter(mapel__gadik_pengajar=user).distinct()


def kelas_for_user(user):
    queryset = Kelas.objects.select_related("kurikulum", "gadik_pembina")
    if user.is_superuser or user.role == CustomUser.Role.ADMIN:
        return queryset
    if user.role == CustomUser.Role.GADIK:
        return queryset.filter(
            Q(gadik_pembina=user) | Q(kurikulum__mata_pelajaran__gadik_pengajar=user)
        ).distinct()
    return queryset.filter(anggota__serdik=user)


@login_required
def profil(request):
    form = ProfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        password_diubah = bool(form.cleaned_data.get("password_baru"))
        user = form.save()
        if password_diubah:
            update_session_auth_hash(request, user)
        messages.success(request, "Profil berhasil diperbarui.")
        return redirect("profil")
    return render(
        request,
        "lms/form.html",
        {
            "form": form,
            "title": "Profil Saya",
            "subtitle": f"Perbarui data profil dan password akun {request.user.get_role_display()} Anda.",
            "button_text": "Simpan profil",
        },
    )


@login_required
def dashboard(request):
    kelas = kelas_for_user(request.user).distinct()
    kelas_ids = kelas.values_list("id", flat=True)
    tugas = Tugas.objects.filter(kelas_id__in=kelas_ids).select_related("kelas", "mapel", "gadik")
    if request.user.role == CustomUser.Role.GADIK:
        tugas = tugas.filter(mapel__gadik_pengajar=request.user).distinct()
    context = {
        "kelas": kelas[:6],
        "jumlah_kelas": kelas.count(),
        "jumlah_modul": ModulBelajar.objects.filter(kelas_id__in=kelas_ids).count(),
        "jumlah_tugas": tugas.count(),
        "tugas_terdekat": tugas.order_by("deadline")[:5],
    }
    if request.user.role == CustomUser.Role.SERDIK:
        pengumpulan = PengumpulanTugas.objects.filter(serdik=request.user)
        context.update(
            jumlah_dinilai=pengumpulan.filter(status=PengumpulanTugas.Status.DINILAI).count(),
            rata_nilai=pengumpulan.aggregate(rata=Avg("nilai"))["rata"],
        )
    elif request.user.role == CustomUser.Role.GADIK:
        context["perlu_dinilai"] = PengumpulanTugas.objects.filter(
            tugas__gadik=request.user, nilai__isnull=True
        ).count()
    else:
        context["jumlah_pengguna"] = CustomUser.objects.count()
    return render(request, "lms/dashboard.html", context)


@login_required
def daftar_kelas(request):
    kelas = kelas_for_user(request.user).annotate(
        jumlah_anggota=Count("anggota", distinct=True),
        jumlah_modul=Count("modul", distinct=True),
    )
    return render(request, "lms/daftar_kelas.html", {"kelas": kelas})


@role_required(CustomUser.Role.ADMIN)
def daftar_siswa(request):
    siswa = CustomUser.objects.filter(role=CustomUser.Role.SERDIK).prefetch_related(
        "keanggotaan_kelas__kelas"
    ).order_by("nama_lengkap", "nip_nrp")
    return render(request, "lms/daftar_siswa.html", {"siswa": siswa})


@role_required(CustomUser.Role.ADMIN)
def tambah_siswa(request):
    form = SiswaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Data dan akun siswa berhasil ditambahkan.")
        return redirect("daftar_siswa")
    return render(
        request,
        "lms/form.html",
        {"form": form, "title": "Tambah Siswa", "button_text": "Simpan siswa"},
    )


@role_required(CustomUser.Role.ADMIN)
def ubah_siswa(request, pk):
    siswa = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Role.SERDIK)
    form = EditSiswaForm(request.POST or None, instance=siswa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Data siswa berhasil diperbarui.")
        return redirect("daftar_siswa")
    return render(
        request,
        "lms/form.html",
        {"form": form, "title": f"Edit Siswa - {siswa.display_name}", "button_text": "Simpan perubahan"},
    )


@role_required(CustomUser.Role.ADMIN)
@transaction.atomic
def kelola_anggota_kelas(request, pk):
    kelas = get_object_or_404(Kelas.objects.select_related("kurikulum"), pk=pk)
    form = TambahAnggotaKelasForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        AnggotaKelas.objects.bulk_create(
            [AnggotaKelas(kelas=kelas, serdik=siswa) for siswa in form.cleaned_data["siswa"]]
        )
        messages.success(request, f"{len(form.cleaned_data['siswa'])} siswa berhasil dimasukkan ke kelas.")
        return redirect("kelola_anggota_kelas", pk=kelas.pk)

    pencarian = request.GET.get("q", "").strip()
    anggota = kelas.anggota.select_related("serdik").order_by("serdik__nama_lengkap", "serdik__nip_nrp")
    if pencarian:
        anggota = anggota.filter(serdik__nama_lengkap__icontains=pencarian)
    return render(
        request,
        "lms/kelola_anggota_kelas.html",
        {"kelas": kelas, "form": form, "anggota": anggota, "pencarian": pencarian},
    )


@role_required(CustomUser.Role.ADMIN)
@require_POST
def hapus_anggota_kelas(request, pk, anggota_pk):
    anggota = get_object_or_404(AnggotaKelas, pk=anggota_pk, kelas_id=pk)
    nama_siswa = anggota.serdik.display_name
    anggota.delete()
    messages.success(request, f"{nama_siswa} berhasil dikeluarkan dari kelas.")
    return redirect("kelola_anggota_kelas", pk=pk)


@login_required
def detail_kelas(request, pk):
    kelas = get_object_or_404(kelas_for_user(request.user), pk=pk)
    modul = kelas.modul.select_related("mapel", "gadik").prefetch_related("mapel__gadik_pengajar")
    tugas = kelas.tugas.select_related("mapel", "gadik")
    anggota = kelas.anggota.select_related("serdik").order_by("serdik__nama_lengkap", "serdik__nip_nrp")
    mapel_diajar = MataPelajaran.objects.none()
    modul_per_mapel = []
    if request.user.role == CustomUser.Role.SERDIK:
        kelompok_mapel = {}
        for item in modul:
            kelompok = kelompok_mapel.get(item.mapel_id)
            if kelompok is None:
                kelompok = {
                    "mapel": item.mapel,
                    "gadik": list(item.mapel.gadik_pengajar.all()),
                    "modul": [],
                }
                kelompok_mapel[item.mapel_id] = kelompok
                modul_per_mapel.append(kelompok)
            kelompok["modul"].append(item)
    if request.user.role == CustomUser.Role.GADIK:
        mapel_diajar = kelas.kurikulum.mata_pelajaran.filter(gadik_pengajar=request.user)
        tugas = tugas.filter(mapel__gadik_pengajar=request.user)
    return render(
        request,
        "lms/detail_kelas.html",
        {
            "kelas": kelas,
            "modul": modul,
            "modul_per_mapel": modul_per_mapel,
            "tugas": tugas,
            "anggota": anggota,
            "mapel_diajar": mapel_diajar,
        },
    )


@role_required(CustomUser.Role.ADMIN)
def pengelolaan_admin(request):
    modul_unik = {}
    for modul in ModulBelajar.objects.select_related("mapel").order_by("-created_at"):
        modul_unik.setdefault((modul.mapel_id, modul.file_modul.name), modul)
    context = {
        "kurikulum": Kurikulum.objects.all()[:5],
        "kelas": Kelas.objects.select_related("kurikulum", "gadik_pembina")[:5],
        "gadik": CustomUser.objects.filter(role=CustomUser.Role.GADIK).order_by("nama_lengkap")[:5],
        "mapel": MataPelajaran.objects.select_related("kurikulum").prefetch_related("gadik_pengajar")[:5],
        "modul": list(modul_unik.values())[:5],
        "jumlah_kurikulum": Kurikulum.objects.count(),
        "jumlah_kelas": Kelas.objects.count(),
        "jumlah_gadik": CustomUser.objects.filter(role=CustomUser.Role.GADIK).count(),
        "jumlah_mapel": MataPelajaran.objects.count(),
        "jumlah_modul": len(modul_unik),
    }
    return render(request, "lms/pengelolaan_admin.html", context)


@role_required(CustomUser.Role.ADMIN)
def daftar_kurikulum(request):
    kurikulum = Kurikulum.objects.annotate(
        jumlah_mapel=Count("mata_pelajaran", distinct=True),
        jumlah_kelas=Count("kelas", distinct=True),
        jumlah_siswa=Count("kelas__anggota__serdik", distinct=True),
    )
    return render(request, "lms/daftar_kurikulum.html", {"kurikulum": kurikulum})


@role_required(CustomUser.Role.ADMIN)
@require_POST
def ubah_status_kurikulum(request, pk):
    kurikulum = get_object_or_404(Kurikulum, pk=pk)
    kurikulum.is_active = request.POST.get("is_active") == "on"
    kurikulum.save(update_fields=["is_active"])
    status = "aktif" if kurikulum.is_active else "tidak aktif"
    messages.success(request, f"Kurikulum {kurikulum.nama_kurikulum} sekarang {status}.")
    return redirect("daftar_kurikulum")


@role_required(CustomUser.Role.ADMIN)
def daftar_gadik(request):
    gadik = CustomUser.objects.filter(role=CustomUser.Role.GADIK).annotate(
        jumlah_kelas=Count("kelas_binaan", distinct=True),
        jumlah_mapel=Count("mata_pelajaran_diampu", distinct=True),
        jumlah_modul=Count("modul_dibuat", distinct=True),
    ).order_by("nama_lengkap", "nip_nrp")
    return render(request, "lms/daftar_gadik.html", {"gadik": gadik})


@role_required(CustomUser.Role.ADMIN)
def ubah_gadik(request, pk):
    gadik = get_object_or_404(CustomUser, pk=pk, role=CustomUser.Role.GADIK)
    form = EditGadikForm(request.POST or None, instance=gadik)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Data Gadik berhasil diperbarui.")
        return redirect("daftar_gadik")
    return render(
        request,
        "lms/form.html",
        {"form": form, "title": f"Edit Gadik - {gadik.display_name}", "button_text": "Simpan perubahan"},
    )


@role_required(CustomUser.Role.ADMIN)
def daftar_mata_pelajaran(request):
    pencarian = request.GET.get("q", "").strip()
    mapel = MataPelajaran.objects.select_related("kurikulum").prefetch_related("gadik_pengajar", "modul")
    if pencarian:
        mapel = mapel.filter(nama_mapel__icontains=pencarian)
    for item in mapel:
        modul_unik = {}
        for modul in item.modul.all():
            modul_unik.setdefault(modul.file_modul.name, modul)
        item.modul_tersedia = list(modul_unik.values())
    return render(request, "lms/daftar_mata_pelajaran.html", {"mapel": mapel, "pencarian": pencarian})


@role_required(CustomUser.Role.ADMIN)
def tambah_mata_pelajaran(request):
    form = MataPelajaranForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mata pelajaran dan Gadik pengajar berhasil ditambahkan.")
        return redirect("daftar_mata_pelajaran")
    return render(
        request,
        "lms/form.html",
        {
            "form": form,
            "title": "Tambah Mata Pelajaran",
            "subtitle": "Pilih satu atau beberapa Gadik yang mengajar mata pelajaran ini.",
            "button_text": "Simpan mata pelajaran",
        },
    )


@role_required(CustomUser.Role.ADMIN)
def tambah_kurikulum(request):
    form = KurikulumForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Kurikulum berhasil ditambahkan.")
        return redirect("daftar_kurikulum")
    return render(request, "lms/form.html", {"form": form, "title": "Tambah Kurikulum", "button_text": "Simpan kurikulum"})


@role_required(CustomUser.Role.ADMIN)
def tambah_kelas(request):
    form = KelasForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Kelas berhasil ditambahkan.")
        return redirect("daftar_kelas")
    return render(request, "lms/form.html", {"form": form, "title": "Tambah Kelas", "button_text": "Simpan kelas"})


@role_required(CustomUser.Role.ADMIN)
def tambah_gadik(request):
    form = GadikForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Akun Gadik berhasil ditambahkan.")
        return redirect("pengelolaan_admin")
    return render(request, "lms/form.html", {"form": form, "title": "Tambah Gadik", "button_text": "Buat akun Gadik"})


@role_required(CustomUser.Role.ADMIN)
@transaction.atomic
def tambah_modul_admin(request):
    mapel_terpilih = None
    if request.GET.get("mapel"):
        mapel_terpilih = get_object_or_404(MataPelajaran, pk=request.GET["mapel"])
    form = AdminModulBelajarForm(
        request.POST or None,
        request.FILES or None,
        mapel_terpilih=mapel_terpilih,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        gadik = data["mapel"].gadik_pengajar.filter(is_active=True).order_by("pk").first()
        kelas = list(data["kurikulum"].kelas.all())
        modul_pertama = ModulBelajar.objects.create(
            kelas=kelas[0],
            mapel=data["mapel"],
            gadik=gadik,
            judul=data["judul"],
            deskripsi=data["deskripsi"],
            file_modul=data["file_modul"],
        )
        for kelas_item in kelas[1:]:
            ModulBelajar.objects.create(
                kelas=kelas_item,
                mapel=data["mapel"],
                gadik=gadik,
                judul=data["judul"],
                deskripsi=data["deskripsi"],
                file_modul=modul_pertama.file_modul.name,
            )
        messages.success(request, f"Modul berhasil dibagikan ke {len(kelas)} kelas dalam kurikulum tersebut.")
        return redirect("pengelolaan_admin")
    return render(
        request,
        "lms/form.html",
        {
            "form": form,
            "title": f"Tambah Modul {mapel_terpilih.nama_mapel}" if mapel_terpilih else "Bagikan Modul ke Kurikulum",
            "subtitle": "Satu unggahan akan tersedia di seluruh kelas pada kurikulum yang dipilih.",
            "button_text": "Bagikan modul",
        },
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK, CustomUser.Role.SERDIK)
def daftar_modul(request):
    modul_unik = {}
    queryset = ModulBelajar.objects.select_related("mapel", "mapel__kurikulum", "gadik").order_by(
        "-created_at"
    )
    for modul in queryset:
        modul_unik.setdefault((modul.mapel_id, modul.file_modul.name), modul)
    modul_per_mapel = []
    kelompok_mapel = {}
    for modul in modul_unik.values():
        kelompok = kelompok_mapel.get(modul.mapel_id)
        if kelompok is None:
            kelompok = {"mapel": modul.mapel, "modul": []}
            kelompok_mapel[modul.mapel_id] = kelompok
            modul_per_mapel.append(kelompok)
        kelompok["modul"].append(modul)
    return render(request, "lms/daftar_modul.html", {"modul_per_mapel": modul_per_mapel})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
@transaction.atomic
def buat_modul(request):
    form = ModulBelajarForm(request.POST or None, request.FILES or None, gadik=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        kelas = list(data["mapel"].kurikulum.kelas.all())
        modul_pertama = ModulBelajar.objects.create(
            kelas=kelas[0],
            mapel=data["mapel"],
            gadik=request.user,
            judul=data["judul"],
            deskripsi=data["deskripsi"],
            file_modul=data["file_modul"],
        )
        for kelas_item in kelas[1:]:
            ModulBelajar.objects.create(
                kelas=kelas_item,
                mapel=data["mapel"],
                gadik=request.user,
                judul=data["judul"],
                deskripsi=data["deskripsi"],
                file_modul=modul_pertama.file_modul.name,
            )
        messages.success(request, f"Modul berhasil dibagikan ke {len(kelas)} kelas.")
        return redirect("daftar_modul")
    return render(
        request,
        "lms/form.html",
        {
            "form": form,
            "title": "Tambah Modul",
            "subtitle": "Satu unggahan akan tersedia di seluruh kelas pada kurikulum mata pelajaran.",
            "button_text": "Bagikan modul",
        },
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def ubah_modul(request, pk):
    queryset = ModulBelajar.objects.all()
    if not is_admin(request.user):
        queryset = queryset.filter(gadik=request.user)
    modul = get_object_or_404(queryset, pk=pk)
    form = ModulBelajarForm(request.POST or None, request.FILES or None, instance=modul, gadik=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modul belajar berhasil diperbarui.")
        return redirect("detail_kelas", pk=modul.kelas_id)
    return render(request, "lms/form.html", {"form": form, "title": "Ubah Modul", "button_text": "Simpan perubahan"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def hapus_modul(request, pk):
    queryset = ModulBelajar.objects.all()
    if not is_admin(request.user):
        queryset = queryset.filter(gadik=request.user)
    modul = get_object_or_404(queryset, pk=pk)
    if request.method == "POST":
        kelas_id = modul.kelas_id
        modul.delete()
        messages.success(request, "Modul belajar berhasil dihapus.")
        return redirect("detail_kelas", pk=kelas_id)
    return render(request, "lms/confirm_delete.html", {"object": modul, "type": "modul"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def buat_tugas(request):
    kelas = None
    kelas_id = request.GET.get("kelas")
    if kelas_id:
        kelas = get_object_or_404(kelas_for_user(request.user), pk=kelas_id)
    form = TugasForm(
        request.POST or None,
        request.FILES or None,
        gadik=request.user,
        kelas=kelas,
        initial={"kelas": kelas} if kelas else None,
    )
    if request.method == "POST" and form.is_valid():
        tugas = form.save(commit=False)
        tugas.gadik = request.user
        tugas.full_clean()
        tugas.save()
        messages.success(request, "Tugas berhasil diterbitkan.")
        return redirect("detail_tugas", pk=tugas.pk)
    return render(request, "lms/form.html", {"form": form, "title": "Buat Tugas", "button_text": "Terbitkan tugas"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def ubah_tugas(request, pk):
    queryset = Tugas.objects.all()
    if not is_admin(request.user):
        queryset = queryset.filter(gadik=request.user)
    tugas = get_object_or_404(queryset, pk=pk)
    form = TugasForm(request.POST or None, request.FILES or None, instance=tugas, gadik=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tugas berhasil diperbarui.")
        return redirect("detail_tugas", pk=tugas.pk)
    return render(request, "lms/form.html", {"form": form, "title": "Ubah Tugas", "button_text": "Simpan perubahan"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def hapus_tugas(request, pk):
    queryset = Tugas.objects.all()
    if not is_admin(request.user):
        queryset = queryset.filter(gadik=request.user)
    tugas = get_object_or_404(queryset, pk=pk)
    if request.method == "POST":
        kelas_id = tugas.kelas_id
        tugas.delete()
        messages.success(request, "Tugas berhasil dihapus.")
        return redirect("detail_kelas", pk=kelas_id)
    return render(request, "lms/confirm_delete.html", {"object": tugas, "type": "tugas"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK, CustomUser.Role.SERDIK)
def daftar_ujian(request):
    ujian = Ujian.objects.select_related("kelas", "mapel", "gadik").annotate(
        jumlah_pengumpulan=Count("pengumpulan", filter=Q(pengumpulan__submitted_at__isnull=False), distinct=True)
    )
    if request.user.role == CustomUser.Role.GADIK:
        ujian = ujian.filter(mapel__gadik_pengajar=request.user).distinct()
    elif request.user.role == CustomUser.Role.SERDIK:
        ujian = ujian.filter(kelas__anggota__serdik=request.user)
        percobaan = {
            item.ujian_id: item
            for item in PengumpulanUjian.objects.filter(serdik=request.user).select_related("ujian")
        }
        ujian = list(ujian)
        for item in ujian:
            item.percobaan_siswa = percobaan.get(item.pk)
            item.jumlah_soal = item.soal_esai.count() if item.metode == Ujian.Metode.ESAI else item.soal_pilihan_ganda.count()
    if request.user.role in [CustomUser.Role.ADMIN, CustomUser.Role.GADIK] or request.user.is_superuser:
        ujian = list(ujian)
        for item in ujian:
            item.bisa_dikelola = True
            item.jumlah_soal = item.soal_esai.count() if item.metode == Ujian.Metode.ESAI else item.soal_pilihan_ganda.count()

    ujian_list = list(ujian)
    ujian_aktif = [item for item in ujian_list if not item.sudah_selesai]
    ujian_selesai = [item for item in ujian_list if item.sudah_selesai]

    return render(
        request,
        "lms/daftar_ujian.html",
        {
            "ujian": ujian_list,
            "ujian_aktif": ujian_aktif,
            "ujian_selesai": ujian_selesai,
        },
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def buat_ujian(request):
    form = UjianForm(request.POST or None, gadik=request.user)
    if request.method == "POST" and form.is_valid():
        ujian = form.save(commit=False)
        ujian.gadik = request.user
        ujian.full_clean()
        ujian.save()
        messages.success(request, "Ujian berhasil diterbitkan.")
        return redirect("daftar_ujian")
    return render(request, "lms/form_ujian.html", {"form": form, "title": "Buat Ujian"})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def ubah_ujian(request, pk):
    ujian = get_object_or_404(ujian_for_manager(request.user), pk=pk)
    form = UjianForm(request.POST or None, instance=ujian, gadik=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pengaturan ujian berhasil diperbarui.")
        return redirect("daftar_ujian")
    return render(
        request,
        "lms/form_ujian.html",
        {"form": form, "title": "Edit Ujian", "ujian": ujian},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def kelola_soal_esai(request, pk):
    queryset = ujian_for_manager(request.user, Ujian.objects.filter(metode=Ujian.Metode.ESAI))
    ujian = get_object_or_404(queryset, pk=pk)
    nomor_berikutnya = (ujian.soal_esai.order_by("-urutan").values_list("urutan", flat=True).first() or 0) + 1
    form = SoalUjianEsaiForm(
        request.POST or None,
        ujian=ujian,
        initial={"urutan": nomor_berikutnya},
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Soal esai dan kunci jawaban berhasil ditambahkan.")
        return redirect("kelola_soal_esai", pk=ujian.pk)
    return render(
        request,
        "lms/kelola_soal_esai.html",
        {"ujian": ujian, "form": form, "soal": ujian.soal_esai.all()},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
@require_POST
def hapus_soal_esai(request, pk, soal_pk):
    queryset = ujian_for_manager(request.user, Ujian.objects.filter(metode=Ujian.Metode.ESAI))
    ujian = get_object_or_404(queryset, pk=pk)
    soal = get_object_or_404(SoalUjianEsai, pk=soal_pk, ujian=ujian)
    soal.delete()
    messages.success(request, "Soal esai berhasil dihapus.")
    return redirect("kelola_soal_esai", pk=ujian.pk)


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def kelola_soal_pilihan_ganda(request, pk):
    queryset = ujian_for_manager(request.user, Ujian.objects.filter(metode=Ujian.Metode.PILIHAN_GANDA))
    ujian = get_object_or_404(queryset, pk=pk)
    nomor_berikutnya = (ujian.soal_pilihan_ganda.order_by("-urutan").values_list("urutan", flat=True).first() or 0) + 1
    form = SoalUjianPilihanGandaForm(
        request.POST or None,
        ujian=ujian,
        initial={"urutan": nomor_berikutnya},
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Soal pilihan ganda dan kunci jawaban berhasil ditambahkan.")
        return redirect("kelola_soal_pilihan_ganda", pk=ujian.pk)
    return render(
        request,
        "lms/kelola_soal_pilihan_ganda.html",
        {"ujian": ujian, "form": form, "soal": ujian.soal_pilihan_ganda.prefetch_related("opsi")},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
@require_POST
def hapus_soal_pilihan_ganda(request, pk, soal_pk):
    queryset = ujian_for_manager(request.user, Ujian.objects.filter(metode=Ujian.Metode.PILIHAN_GANDA))
    ujian = get_object_or_404(queryset, pk=pk)
    soal = get_object_or_404(SoalUjianPilihanGanda, pk=soal_pk, ujian=ujian)
    soal.delete()
    messages.success(request, "Soal pilihan ganda berhasil dihapus.")
    return redirect("kelola_soal_pilihan_ganda", pk=ujian.pk)


@role_required(CustomUser.Role.SERDIK)
@transaction.atomic
@require_POST
def mulai_ujian_esai(request, pk):
    ujian = get_object_or_404(
        Ujian.objects.filter(kelas__anggota__serdik=request.user),
        pk=pk,
    )
    if not ujian.sudah_mulai:
        messages.error(request, "Ujian belum dapat dimulai.")
        return redirect("daftar_ujian")
    if ujian.sudah_selesai:
        messages.error(request, "Batas akhir ujian telah terlewat.")
        return redirect("daftar_ujian")
    punya_soal = ujian.soal_esai.exists() if ujian.metode == Ujian.Metode.ESAI else ujian.soal_pilihan_ganda.exists()
    if not punya_soal:
        messages.error(request, "Soal ujian belum tersedia.")
        return redirect("daftar_ujian")
    percobaan, dibuat = PengumpulanUjian.objects.get_or_create(
        ujian=ujian,
        serdik=request.user,
        defaults={"started_at": timezone.now()},
    )
    if percobaan.sudah_dikumpulkan:
        messages.info(request, "Ujian ini sudah Anda kumpulkan.")
        return redirect("daftar_ujian")
    if not dibuat and percobaan.waktu_habis:
        messages.error(request, "Waktu pengerjaan ujian Anda telah habis.")
        return redirect("daftar_ujian")
    return redirect("kerjakan_ujian_esai", pk=ujian.pk)


@role_required(CustomUser.Role.SERDIK)
@transaction.atomic
def kerjakan_ujian_esai(request, pk):
    ujian = get_object_or_404(
        Ujian.objects.filter(kelas__anggota__serdik=request.user),
        pk=pk,
    )
    percobaan = PengumpulanUjian.objects.filter(ujian=ujian, serdik=request.user).first()
    if not percobaan:
        messages.info(request, "Konfirmasi mulai ujian terlebih dahulu.")
        return redirect("daftar_ujian")
    if percobaan.sudah_dikumpulkan:
        messages.info(request, "Ujian ini sudah Anda kumpulkan.")
        return redirect("daftar_ujian")
    if percobaan.waktu_habis:
        messages.error(request, "Waktu pengerjaan ujian Anda telah habis dan ujian dikunci.")
        return redirect("daftar_ujian")
    if ujian.metode == Ujian.Metode.PILIHAN_GANDA:
        return kerjakan_ujian_pilihan_ganda(request, ujian, percobaan)
    soal = list(ujian.soal_esai.all())
    if not soal:
        messages.error(request, "Soal ujian belum tersedia.")
        return redirect("daftar_ujian")
    form = JawabanUjianEsaiForm(request.POST or None, soal=soal)
    if request.method == "POST" and form.is_valid():
        percobaan = PengumpulanUjian.objects.select_for_update().get(pk=percobaan.pk)
        if percobaan.waktu_habis:
            messages.error(request, "Waktu pengerjaan ujian Anda telah habis dan jawaban tidak dapat dikumpulkan.")
            return redirect("daftar_ujian")
        percobaan.submitted_at = timezone.now()
        percobaan.save(update_fields=["submitted_at"])
        JawabanUjianEsai.objects.bulk_create(
            [
                JawabanUjianEsai(
                    pengumpulan=percobaan,
                    soal=item,
                    jawaban=form.cleaned_data[f"soal_{item.pk}"],
                )
                for item in soal
            ]
        )
        percobaan.nilai_otomatis()
        if percobaan.nilai is not None:
            messages.success(request, f"Ujian berhasil dikumpulkan. Nilai Anda: {percobaan.nilai}.")
        else:
            messages.success(request, "Ujian berhasil dikumpulkan dan menunggu konfirmasi penilaian Gadik.")
        return redirect("daftar_ujian")
    return render(
        request,
        "lms/kerjakan_ujian_esai.html",
        {"ujian": ujian, "percobaan": percobaan, "soal_dan_field": list(zip(soal, form)), "form": form},
    )


def kerjakan_ujian_pilihan_ganda(request, ujian, percobaan):
    soal = list(ujian.soal_pilihan_ganda.prefetch_related("opsi"))
    if not soal:
        messages.error(request, "Soal ujian belum tersedia.")
        return redirect("daftar_ujian")
    form = JawabanUjianPilihanGandaForm(request.POST or None, soal=soal)
    if request.method == "POST" and form.is_valid():
        percobaan = PengumpulanUjian.objects.select_for_update().get(pk=percobaan.pk)
        if percobaan.waktu_habis:
            messages.error(request, "Waktu pengerjaan ujian Anda telah habis dan jawaban tidak dapat dikumpulkan.")
            return redirect("daftar_ujian")
        percobaan.submitted_at = timezone.now()
        percobaan.save(update_fields=["submitted_at"])
        JawabanUjianPilihanGanda.objects.bulk_create(
            [
                JawabanUjianPilihanGanda(
                    pengumpulan=percobaan,
                    soal=item,
                    opsi_id=form.cleaned_data[f"soal_{item.pk}"],
                )
                for item in soal
            ]
        )
        percobaan.nilai_pilihan_ganda()
        messages.success(request, f"Ujian berhasil dikumpulkan. Nilai Anda: {percobaan.nilai}.")
        return redirect("daftar_ujian")
    return render(
        request,
        "lms/kerjakan_ujian_pilihan_ganda.html",
        {"ujian": ujian, "percobaan": percobaan, "soal_dan_field": list(zip(soal, form)), "form": form},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK, CustomUser.Role.SERDIK)
def hasil_ujian(request, pk):
    if request.user.role == CustomUser.Role.SERDIK:
        if request.method == "POST":
            raise PermissionDenied
        ujian = get_object_or_404(Ujian.objects.filter(kelas__anggota__serdik=request.user), pk=pk)
        pengumpulan = get_object_or_404(
            ujian.pengumpulan.filter(serdik=request.user, submitted_at__isnull=False).select_related("serdik")
        )
        if ujian.metode == Ujian.Metode.PILIHAN_GANDA:
            jawaban = list(
                pengumpulan.jawaban_pilihan_ganda.select_related("opsi", "soal").prefetch_related(
                    "soal__opsi"
                ).order_by("soal__urutan")
            )
        else:
            jumlah_soal = ujian.soal_esai.count()
            nilai_maksimal = (Decimal("100") / Decimal(jumlah_soal)) if jumlah_soal else Decimal("0")
            jawaban = list(pengumpulan.jawaban_esai.select_related("soal").order_by("soal__urutan"))
            for item in jawaban:
                item.nilai_maksimal = nilai_maksimal.quantize(Decimal("0.01"))
        return render(
            request,
            "lms/hasil_ujian.html",
            {"ujian": ujian, "rows": [{"pengumpulan": pengumpulan, "jawaban": jawaban}], "is_student_result": True},
        )

    queryset = ujian_for_manager(request.user)
    ujian = get_object_or_404(queryset, pk=pk)
    pengumpulan_queryset = ujian.pengumpulan.filter(submitted_at__isnull=False).select_related("serdik").order_by(
        "serdik__nama_lengkap", "serdik__username"
    )
    pengumpulan_terpilih = request.GET.get("pengumpulan") or request.POST.get("pengumpulan")
    if not pengumpulan_terpilih:
        return render(
            request,
            "lms/hasil_ujian.html",
            {"ujian": ujian, "pengumpulan_rows": pengumpulan_queryset, "show_submission_table": True},
        )
    if ujian.metode == Ujian.Metode.PILIHAN_GANDA:
        pengumpulan = get_object_or_404(
            pengumpulan_queryset.prefetch_related(
                "jawaban_pilihan_ganda__soal__opsi", "jawaban_pilihan_ganda__opsi"
            ),
            pk=pengumpulan_terpilih,
        )
        rows = [
            {
                "pengumpulan": pengumpulan,
                "jawaban": list(pengumpulan.jawaban_pilihan_ganda.order_by("soal__urutan")),
            }
        ]
        return render(request, "lms/hasil_ujian.html", {"ujian": ujian, "rows": rows})
    jumlah_soal = ujian.soal_esai.count()
    nilai_maksimal = (Decimal("100") / Decimal(jumlah_soal)) if jumlah_soal else Decimal("0")
    if request.method == "POST":
        pengumpulan = get_object_or_404(pengumpulan_queryset, pk=pengumpulan_terpilih)
        jawaban = list(pengumpulan.jawaban_esai.select_related("soal").order_by("soal__urutan"))
        skor_valid = True
        for item in jawaban:
            if item.soal.pemeriksaan == SoalUjianEsai.Pemeriksaan.OTOMATIS:
                continue
            try:
                skor = Decimal(request.POST.get(f"skor_{item.pk}", ""))
            except InvalidOperation:
                skor_valid = False
                break
            if skor < 0 or skor > nilai_maksimal:
                skor_valid = False
                break
            item.skor = skor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if skor_valid and all(item.skor is not None for item in jawaban):
            JawabanUjianEsai.objects.bulk_update(jawaban, ["skor"])
            pengumpulan.nilai = min(sum((item.skor for item in jawaban), Decimal("0")), Decimal("100"))
            pengumpulan.save(update_fields=["nilai"])
            messages.success(request, f"Nilai {pengumpulan.serdik.display_name} berhasil disimpan.")
            return redirect(f"{request.path}?pengumpulan={pengumpulan.pk}")
        messages.error(request, f"Setiap skor wajib diisi antara 0 dan {nilai_maksimal:.2f}.")
    rows = []
    for pengumpulan in pengumpulan_queryset.filter(pk=pengumpulan_terpilih).prefetch_related(
        "jawaban_esai__soal"
    ):
        jawaban = list(pengumpulan.jawaban_esai.order_by("soal__urutan"))
        for item in jawaban:
            item.nilai_maksimal = nilai_maksimal.quantize(Decimal("0.01"))
        rows.append(
            {
                "pengumpulan": pengumpulan,
                "jawaban": jawaban,
            }
        )
    if not rows:
        raise PermissionDenied
    return render(request, "lms/hasil_ujian.html", {"ujian": ujian, "rows": rows})


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def export_hasil_ujian_excel(request, pk):
    ujian = get_object_or_404(ujian_for_manager(request.user), pk=pk)
    excel_buffer = generate_exam_excel(ujian)
    safe_judul = slugify(ujian.judul) or "ujian"
    safe_kelas = slugify(ujian.kelas.nama_kelas) or "kelas"
    filename = f"Hasil_Ujian_{safe_judul}_{safe_kelas}.xlsx"
    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def export_hasil_ujian_pdf(request, pk):
    ujian = get_object_or_404(ujian_for_manager(request.user), pk=pk)
    pdf_buffer = generate_exam_pdf(ujian)
    safe_judul = slugify(ujian.judul) or "ujian"
    safe_kelas = slugify(ujian.kelas.nama_kelas) or "kelas"
    filename = f"Hasil_Ujian_{safe_judul}_{safe_kelas}.pdf"
    response = HttpResponse(
        pdf_buffer.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def detail_tugas(request, pk):
    tugas_queryset = Tugas.objects.select_related("kelas", "mapel", "gadik").filter(
        kelas__in=kelas_for_user(request.user)
    )
    if request.user.role == CustomUser.Role.GADIK:
        tugas_queryset = tugas_queryset.filter(mapel__gadik_pengajar=request.user)
    tugas = get_object_or_404(tugas_queryset, pk=pk)
    pengumpulan = None
    if request.user.role == CustomUser.Role.SERDIK:
        pengumpulan = PengumpulanTugas.objects.select_related("dinilai_oleh").filter(
            tugas=tugas, serdik=request.user
        ).first()
    return render(request, "lms/detail_tugas.html", {"tugas": tugas, "pengumpulan": pengumpulan})


@role_required(CustomUser.Role.SERDIK)
def kumpulkan_tugas(request, pk):
    tugas = get_object_or_404(Tugas.objects.filter(kelas__anggota__serdik=request.user), pk=pk)
    pengumpulan = PengumpulanTugas.objects.filter(tugas=tugas, serdik=request.user).first()
    if pengumpulan and pengumpulan.status == PengumpulanTugas.Status.DINILAI:
        messages.error(request, "Tugas yang sudah dinilai tidak dapat diunggah ulang.")
        return redirect("detail_tugas", pk=tugas.pk)
    form = PengumpulanTugasForm(request.POST or None, request.FILES or None, instance=pengumpulan)
    if request.method == "POST" and form.is_valid():
        pengumpulan = form.save(commit=False)
        pengumpulan.tugas = tugas
        pengumpulan.serdik = request.user
        if pengumpulan.pk:
            pengumpulan.submitted_at = timezone.now()
        pengumpulan.full_clean()
        pengumpulan.save()
        messages.success(request, "Tugas berhasil dikumpulkan.")
        return redirect("detail_tugas", pk=tugas.pk)
    return render(
        request,
        "lms/form.html",
        {"form": form, "title": "Kumpulkan Tugas", "button_text": "Kirim tugas", "tugas": tugas},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def daftar_pengumpulan(request, pk):
    queryset = Tugas.objects.all()
    if not is_admin(request.user):
        queryset = queryset.filter(mapel__gadik_pengajar=request.user).distinct()
    tugas = get_object_or_404(queryset, pk=pk)
    pengumpulan = list(tugas.pengumpulan.select_related("serdik"))
    serdik_sudah_mengumpulkan = [item.serdik_id for item in pengumpulan]
    belum_mengumpulkan = tugas.kelas.anggota.select_related("serdik").exclude(
        serdik_id__in=serdik_sudah_mengumpulkan
    ).order_by("serdik__nama_lengkap", "serdik__nip_nrp")
    return render(
        request,
        "lms/daftar_pengumpulan.html",
        {
            "tugas": tugas,
            "pengumpulan": pengumpulan,
            "belum_mengumpulkan": belum_mengumpulkan,
        },
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.GADIK)
def nilai_pengumpulan(request, pk):
    pengumpulan = get_object_or_404(
        PengumpulanTugas.objects.select_related("tugas", "tugas__mapel", "serdik"),
        pk=pk,
    )
    if not is_admin(request.user) and not pengumpulan.tugas.mapel.gadik_pengajar.filter(pk=request.user.pk).exists():
        raise PermissionDenied
    form = PenilaianForm(request.POST or None, instance=pengumpulan)
    if request.method == "POST" and form.is_valid():
        pengumpulan = form.save(commit=False)
        pengumpulan.dinilai_oleh = request.user
        pengumpulan.save()
        messages.success(request, "Nilai dan umpan balik berhasil disimpan.")
        return redirect("daftar_pengumpulan", pk=pengumpulan.tugas_id)
    return render(
        request,
        "lms/form.html",
        {"form": form, "title": f"Nilai: {pengumpulan.serdik.display_name}", "button_text": "Simpan nilai"},
    )


@role_required(CustomUser.Role.ADMIN, CustomUser.Role.SERDIK)
def daftar_nilai(request):
    pengumpulan = PengumpulanTugas.objects.select_related(
        "tugas", "tugas__mapel", "tugas__kelas", "dinilai_oleh"
    )
    pengumpulan_ujian = PengumpulanUjian.objects.select_related(
        "ujian", "ujian__mapel", "ujian__kelas"
    ).filter(submitted_at__isnull=False).order_by("-submitted_at")
    if not is_admin(request.user):
        pengumpulan = pengumpulan.filter(serdik=request.user)
        pengumpulan_ujian = pengumpulan_ujian.filter(serdik=request.user)
    return render(
        request,
        "lms/daftar_nilai.html",
        {"pengumpulan": pengumpulan, "pengumpulan_ujian": pengumpulan_ujian},
    )
