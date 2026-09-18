from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import CustomUser, Kelas, Kurikulum, MataPelajaran, ModulBelajar, OpsiUjianPilihanGanda, PengumpulanTugas, PengumpulanUjian, SoalUjianEsai, SoalUjianPilihanGanda, Tugas, Ujian


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                css_class = "form-select"
            else:
                css_class = "form-control"
            field.widget.attrs["class"] = css_class


class MateriKelasForm(StyledModelForm):
    def clean(self):
        cleaned_data = super().clean()
        kelas = cleaned_data.get("kelas")
        mapel = cleaned_data.get("mapel")
        if kelas and mapel and kelas.kurikulum_id != mapel.kurikulum_id:
            self.add_error("mapel", "Mata pelajaran harus berasal dari kurikulum kelas.")
        return cleaned_data


class ModulBelajarForm(MateriKelasForm):
    class Meta:
        model = ModulBelajar
        fields = ["mapel", "judul", "deskripsi", "file_modul"]
        widgets = {"deskripsi": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, gadik=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gadik:
            if gadik.role == CustomUser.Role.ADMIN or gadik.is_superuser:
                self.fields["mapel"].queryset = MataPelajaran.objects.all()
            else:
                self.fields["mapel"].queryset = MataPelajaran.objects.filter(
                    gadik_pengajar=gadik,
                ).distinct()

    def clean_mapel(self):
        mapel = self.cleaned_data["mapel"]
        if not mapel.kurikulum.kelas.exists():
            raise forms.ValidationError("Kurikulum mata pelajaran ini belum memiliki kelas.")
        return mapel


class TugasForm(MateriKelasForm):
    class Meta:
        model = Tugas
        fields = ["kelas", "mapel", "judul_tugas", "instruksi", "file_lampiran", "deadline", "bobot"]
        widgets = {
            "instruksi": forms.Textarea(attrs={"rows": 5}),
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, gadik=None, kelas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].input_formats = ["%Y-%m-%dT%H:%M"]
        if gadik:
            if gadik.role == CustomUser.Role.ADMIN or gadik.is_superuser:
                self.fields["kelas"].queryset = Kelas.objects.all()
                self.fields["mapel"].queryset = MataPelajaran.objects.all()
            else:
                self.fields["kelas"].queryset = Kelas.objects.filter(
                    Q(gadik_pembina=gadik) | Q(kurikulum__mata_pelajaran__gadik_pengajar=gadik)
                ).distinct()
                self.fields["mapel"].queryset = MataPelajaran.objects.filter(
                    gadik_pengajar=gadik,
                ).distinct()
            if kelas:
                self.fields["mapel"].queryset = self.fields["mapel"].queryset.filter(
                    kurikulum=kelas.kurikulum
                )


class UjianForm(MateriKelasForm):
    class Meta:
        model = Ujian
        fields = [
            "kelas", "mapel", "judul", "metode", "instruksi",
            "waktu_mulai", "waktu_selesai", "durasi_menit",
        ]
        widgets = {
            "metode": forms.RadioSelect(),
            "instruksi": forms.Textarea(attrs={"rows": 4}),
            "waktu_mulai": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "durasi_menit": forms.NumberInput(attrs={"min": 1}),
            "waktu_selesai": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
        labels = {
            "waktu_mulai": "Jam mulai",
            "durasi_menit": "Durasi ujian (menit)",
            "waktu_selesai": "Batas akhir ujian",
        }

    def __init__(self, *args, gadik=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metode"].widget.attrs["class"] = "exam-method-options"
        self.fields["waktu_mulai"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["waktu_selesai"].input_formats = ["%Y-%m-%dT%H:%M"]
        if gadik:
            if gadik.role == CustomUser.Role.ADMIN or gadik.is_superuser:
                self.fields["kelas"].queryset = Kelas.objects.all()
                self.fields["mapel"].queryset = MataPelajaran.objects.all()
            else:
                self.fields["kelas"].queryset = Kelas.objects.filter(
                    Q(gadik_pembina=gadik) | Q(kurikulum__mata_pelajaran__gadik_pengajar=gadik)
                ).distinct()
                self.fields["mapel"].queryset = MataPelajaran.objects.filter(
                    gadik_pengajar=gadik,
                ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        metode = cleaned_data.get("metode")
        if (
            self.instance.pk
            and metode != Ujian.Metode.ESAI
            and self.instance.soal_esai.exists()
        ):
            self.add_error("metode", "Hapus seluruh soal esai sebelum mengubah metode ujian.")
        if (
            self.instance.pk
            and metode != Ujian.Metode.PILIHAN_GANDA
            and self.instance.soal_pilihan_ganda.exists()
        ):
            self.add_error("metode", "Hapus seluruh soal pilihan ganda sebelum mengubah metode ujian.")
        return cleaned_data


class SoalUjianEsaiForm(StyledModelForm):
    class Meta:
        model = SoalUjianEsai
        fields = ["urutan", "pertanyaan", "kunci_jawaban", "pemeriksaan"]
        labels = {
            "urutan": "Nomor soal",
            "kunci_jawaban": "Kunci jawaban / acuan relevansi",
            "pemeriksaan": "Metode pemeriksaan",
        }
        widgets = {
            "urutan": forms.NumberInput(attrs={"min": 1}),
            "pertanyaan": forms.Textarea(attrs={"rows": 4, "placeholder": "Tuliskan pertanyaan esai..."}),
            "kunci_jawaban": forms.Textarea(attrs={"rows": 5, "placeholder": "Tuliskan poin-poin jawaban yang diharapkan..."}),
            "pemeriksaan": forms.RadioSelect(),
        }

    def __init__(self, *args, ujian=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ujian:
            self.instance.ujian = ujian


class SoalUjianPilihanGandaForm(StyledModelForm):
    MAX_OPSI = 8

    jumlah_opsi = forms.IntegerField(
        label="Jumlah opsi",
        min_value=2,
        max_value=MAX_OPSI,
        initial=4,
        widget=forms.NumberInput(attrs={"min": 2, "max": MAX_OPSI}),
    )

    class Meta:
        model = SoalUjianPilihanGanda
        fields = ["urutan", "pertanyaan"]
        labels = {"urutan": "Nomor soal"}
        widgets = {
            "urutan": forms.NumberInput(attrs={"min": 1}),
            "pertanyaan": forms.Textarea(attrs={"rows": 4, "placeholder": "Tuliskan pertanyaan pilihan ganda..."}),
        }

    def __init__(self, *args, ujian=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ujian = ujian
        if ujian:
            self.instance.ujian = ujian
        jumlah_opsi = self.initial.get("jumlah_opsi", 4)
        if self.is_bound:
            try:
                jumlah_opsi = int(self.data.get(self.add_prefix("jumlah_opsi"), jumlah_opsi))
            except (TypeError, ValueError):
                jumlah_opsi = 4
        jumlah_opsi = min(max(jumlah_opsi, 2), self.MAX_OPSI)
        self.fields["jumlah_opsi"].widget.attrs["class"] = "form-control"
        for nomor in range(1, self.MAX_OPSI + 1):
            self.fields[f"opsi_{nomor}"] = forms.CharField(
                label=f"Opsi {nomor}",
                required=False,
                max_length=500,
                widget=forms.TextInput(attrs={"class": "form-control", "placeholder": f"Tulis opsi {nomor}"}),
            )
        self.fields["kunci_jawaban"] = forms.ChoiceField(
            label="Kunci jawaban",
            choices=[(str(nomor), f"Opsi {nomor}") for nomor in range(1, jumlah_opsi + 1)],
            widget=forms.Select(attrs={"class": "form-select"}),
        )

    def clean(self):
        cleaned_data = super().clean()
        jumlah_opsi = cleaned_data.get("jumlah_opsi")
        kunci_jawaban = cleaned_data.get("kunci_jawaban")
        if not jumlah_opsi:
            return cleaned_data
        opsi = []
        for nomor in range(1, jumlah_opsi + 1):
            teks = (cleaned_data.get(f"opsi_{nomor}") or "").strip()
            if not teks:
                self.add_error(f"opsi_{nomor}", "Opsi wajib diisi sesuai jumlah opsi yang dipilih.")
            opsi.append((nomor, teks))
        if kunci_jawaban and int(kunci_jawaban) > jumlah_opsi:
            self.add_error("kunci_jawaban", "Kunci jawaban harus berada dalam jumlah opsi yang dipilih.")
        self.cleaned_options = opsi
        return cleaned_data

    def save(self, commit=True):
        soal = super().save(commit=False)
        if self.ujian:
            soal.ujian = self.ujian
        if commit:
            soal.save()
            kunci_jawaban = int(self.cleaned_data["kunci_jawaban"])
            OpsiUjianPilihanGanda.objects.bulk_create(
                [
                    OpsiUjianPilihanGanda(
                        soal=soal,
                        urutan=nomor,
                        teks=teks,
                        is_kunci=nomor == kunci_jawaban,
                    )
                    for nomor, teks in self.cleaned_options
                ]
            )
        return soal


class JawabanUjianEsaiForm(forms.Form):
    def __init__(self, *args, soal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.soal = list(soal or [])
        for item in self.soal:
            self.fields[f"soal_{item.pk}"] = forms.CharField(
                label=f"Soal {item.urutan}",
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            )


class JawabanUjianPilihanGandaForm(forms.Form):
    def __init__(self, *args, soal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.soal = list(soal or [])
        for item in self.soal:
            self.fields[f"soal_{item.pk}"] = forms.ChoiceField(
                label=f"Soal {item.urutan}",
                choices=[(opsi.pk, opsi.teks) for opsi in item.opsi.all()],
                widget=forms.RadioSelect(),
            )


class PenilaianUjianEsaiForm(StyledModelForm):
    class Meta:
        model = PengumpulanUjian
        fields = ["nilai"]
        labels = {"nilai": "Nilai akhir"}
        widgets = {"nilai": forms.NumberInput(attrs={"min": 0, "max": 100, "step": "0.01"})}

    def clean_nilai(self):
        nilai = self.cleaned_data["nilai"]
        if nilai is None or not 0 <= nilai <= 100:
            raise forms.ValidationError("Nilai harus berada di antara 0 dan 100.")
        return nilai


class PengumpulanTugasForm(StyledModelForm):
    class Meta:
        model = PengumpulanTugas
        fields = ["file_tugas", "catatan_serdik"]
        widgets = {"catatan_serdik": forms.Textarea(attrs={"rows": 3})}


class PenilaianForm(StyledModelForm):
    class Meta:
        model = PengumpulanTugas
        fields = ["nilai", "catatan_gadik"]
        widgets = {
            "nilai": forms.NumberInput(attrs={"min": 0, "max": 100, "step": "0.01"}),
            "catatan_gadik": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_nilai(self):
        nilai = self.cleaned_data["nilai"]
        if nilai is None:
            raise forms.ValidationError("Nilai wajib diisi.")
        return nilai


class KurikulumForm(StyledModelForm):
    class Meta:
        model = Kurikulum
        fields = ["nama_kurikulum", "tahun_ajaran", "is_active"]


class KelasForm(StyledModelForm):
    class Meta:
        model = Kelas
        fields = ["nama_kelas", "kurikulum", "gadik_pembina"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kurikulum"].queryset = Kurikulum.objects.filter(is_active=True)
        self.fields["gadik_pembina"].queryset = CustomUser.objects.filter(role=CustomUser.Role.GADIK)


class SiswaMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, siswa):
        return f"{siswa.nip_nrp or '-'} - {siswa.display_name}"


class TambahAnggotaKelasForm(forms.Form):
    siswa = SiswaMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        help_text="Centang satu atau beberapa siswa yang akan dimasukkan ke kelas.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["siswa"].queryset = CustomUser.objects.filter(
            role=CustomUser.Role.SERDIK,
            is_active=True,
            keanggotaan_kelas__isnull=True,
        ).order_by("nama_lengkap", "nip_nrp")


class MataPelajaranForm(StyledModelForm):
    class Meta:
        model = MataPelajaran
        fields = ["kurikulum", "kode_mapel", "nama_mapel", "gadik_pengajar"]
        widgets = {"gadik_pengajar": forms.CheckboxSelectMultiple()}
        help_texts = {"gadik_pengajar": "Centang satu atau beberapa Gadik yang mengajar mata pelajaran ini."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kurikulum"].queryset = Kurikulum.objects.filter(is_active=True)
        self.fields["gadik_pengajar"].queryset = CustomUser.objects.filter(
            role=CustomUser.Role.GADIK,
            is_active=True,
        ).order_by("nama_lengkap")
        self.fields["gadik_pengajar"].required = True


class GadikForm(UserCreationForm, StyledModelForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ["nama_lengkap", "nip_nrp", "email"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["nip_nrp"]
        user.role = CustomUser.Role.GADIK
        if commit:
            user.save()
        return user


class SiswaForm(UserCreationForm, StyledModelForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ["nip_nrp", "nama_lengkap", "tempat_lahir", "tanggal_lahir", "asal_pengiriman", "alamat"]
        labels = {"nip_nrp": "NOSIS"}
        widgets = {
            "tanggal_lahir": forms.DateInput(attrs={"type": "date"}),
            "alamat": forms.Textarea(attrs={"rows": 3}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["nip_nrp"]
        user.role = CustomUser.Role.SERDIK
        if commit:
            user.save()
        return user


class EditPenggunaForm(StyledModelForm):
    password_baru = forms.CharField(
        required=False,
        label="Password baru",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Kosongkan jika password tidak ingin diubah.",
    )
    konfirmasi_password = forms.CharField(
        required=False,
        label="Konfirmasi password baru",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nip_nrp"].required = True

    def clean(self):
        cleaned_data = super().clean()
        password_baru = cleaned_data.get("password_baru")
        konfirmasi_password = cleaned_data.get("konfirmasi_password")
        if password_baru != konfirmasi_password:
            self.add_error("konfirmasi_password", "Konfirmasi password tidak sama.")
        elif password_baru:
            try:
                password_validation.validate_password(password_baru, self.instance)
            except ValidationError as error:
                self.add_error("password_baru", error)
        return cleaned_data

    def clean_nip_nrp(self):
        nip_nrp = self.cleaned_data["nip_nrp"]
        if CustomUser.objects.exclude(pk=self.instance.pk).filter(username=nip_nrp).exists():
            raise forms.ValidationError("NOSIS/NIP/NRP ini sudah digunakan sebagai akun lain.")
        return nip_nrp

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["nip_nrp"]
        if self.cleaned_data.get("password_baru"):
            user.set_password(self.cleaned_data["password_baru"])
        if commit:
            user.save()
        return user


class EditSiswaForm(EditPenggunaForm):
    class Meta:
        model = CustomUser
        fields = [
            "nip_nrp", "nama_lengkap", "tempat_lahir", "tanggal_lahir",
            "asal_pengiriman", "alamat", "is_active",
        ]
        labels = {"nip_nrp": "NOSIS", "is_active": "Akun aktif"}
        widgets = {
            "tanggal_lahir": forms.DateInput(attrs={"type": "date"}),
            "alamat": forms.Textarea(attrs={"rows": 3}),
        }


class ProfilForm(EditPenggunaForm):
    class Meta:
        model = CustomUser
        fields = [
            "nip_nrp",
            "nama_lengkap",
            "email",
            "tempat_lahir",
            "tanggal_lahir",
            "asal_pengiriman",
            "alamat",
        ]
        labels = {"nip_nrp": "NIP/NRP/NOSIS"}
        widgets = {
            "tanggal_lahir": forms.DateInput(attrs={"type": "date"}),
            "alamat": forms.Textarea(attrs={"rows": 3}),
        }


class EditGadikForm(EditPenggunaForm):
    mata_pelajaran_diajar = forms.ModelMultipleChoiceField(
        queryset=MataPelajaran.objects.none(),
        required=False,
        label="Mata pelajaran yang diajarkan",
        widget=forms.CheckboxSelectMultiple(),
        help_text="Centang mata pelajaran yang diajarkan oleh Gadik ini.",
    )

    class Meta:
        model = CustomUser
        fields = ["nip_nrp", "nama_lengkap", "email", "is_active"]
        labels = {"nip_nrp": "NIP/NRP", "is_active": "Akun aktif"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mata_pelajaran_diajar"].queryset = MataPelajaran.objects.select_related(
            "kurikulum"
        ).order_by("kurikulum__nama_kurikulum", "kode_mapel")
        if self.instance.pk:
            self.fields["mata_pelajaran_diajar"].initial = self.instance.mata_pelajaran_diampu.all()

    def save(self, commit=True):
        gadik = super().save(commit=commit)
        if commit:
            gadik.mata_pelajaran_diampu.set(self.cleaned_data["mata_pelajaran_diajar"])
        return gadik


class AdminModulBelajarForm(StyledModelForm):
    kurikulum = forms.ModelChoiceField(
        queryset=Kurikulum.objects.none(),
        help_text="Modul akan dibagikan ke seluruh kelas dalam kurikulum ini.",
    )

    class Meta:
        model = ModulBelajar
        fields = ["kurikulum", "mapel", "judul", "deskripsi", "file_modul"]
        widgets = {"deskripsi": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, mapel_terpilih=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kurikulum"].queryset = Kurikulum.objects.filter(is_active=True)
        if mapel_terpilih:
            self.fields["kurikulum"].initial = mapel_terpilih.kurikulum
            self.fields["kurikulum"].disabled = True
            self.fields["mapel"].queryset = MataPelajaran.objects.filter(pk=mapel_terpilih.pk)
            self.fields["mapel"].initial = mapel_terpilih
            self.fields["mapel"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        kurikulum = cleaned_data.get("kurikulum")
        mapel = cleaned_data.get("mapel")
        if kurikulum and not kurikulum.kelas.exists():
            self.add_error("kurikulum", "Kurikulum ini belum memiliki kelas.")
        if kurikulum and mapel and mapel.kurikulum_id != kurikulum.id:
            self.add_error("mapel", "Mata pelajaran harus berasal dari kurikulum yang dipilih.")
        if mapel and not mapel.gadik_pengajar.filter(is_active=True).exists():
            self.add_error("mapel", "Mata pelajaran ini belum memiliki Gadik aktif.")
        return cleaned_data
