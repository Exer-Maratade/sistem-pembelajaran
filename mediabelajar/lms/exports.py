import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.utils.text import slugify

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Ujian


def get_exam_summary_data(ujian: Ujian):
    """
    Mengambil data peserta ujian dan pengumpulan secara terstruktur.
    """
    anggota_qs = ujian.kelas.anggota.select_related("serdik").order_by(
        "serdik__nama_lengkap", "serdik__username"
    )
    pengumpulan_qs = ujian.pengumpulan.select_related("serdik").prefetch_related(
        "jawaban_pilihan_ganda__opsi",
        "jawaban_esai",
    )
    pengumpulan_dict = {p.serdik_id: p for p in pengumpulan_qs}

    # Kumpulkan seluruh siswa kelas, plus siswa yang mungkin sudah submit
    students = []
    seen_ids = set()
    for anggota in anggota_qs:
        students.append(anggota.serdik)
        seen_ids.add(anggota.serdik_id)
    for p in pengumpulan_qs:
        if p.serdik_id not in seen_ids:
            students.append(p.serdik)
            seen_ids.add(p.serdik_id)

    students.sort(key=lambda s: (s.nama_lengkap or s.username).casefold())

    if ujian.metode == Ujian.Metode.PILIHAN_GANDA:
        total_soal = ujian.soal_pilihan_ganda.count()
    else:
        total_soal = ujian.soal_esai.count()

    rows = []
    scores = []
    submitted_count = 0

    for idx, serdik in enumerate(students, start=1):
        pengumpulan = pengumpulan_dict.get(serdik.id)
        nip_nrp = serdik.nip_nrp or "-"
        nama = serdik.display_name

        if pengumpulan and pengumpulan.submitted_at:
            submitted_count += 1
            submitted_str = timezone.localtime(pengumpulan.submitted_at).strftime("%d/%m/%Y %H:%M")
            if pengumpulan.nilai is not None:
                status_str = "Selesai (Dinilai)"
                nilai_val = float(pengumpulan.nilai)
                scores.append(nilai_val)
                nilai_str = f"{nilai_val:.2f}"
            else:
                status_str = "Menunggu Penilaian"
                nilai_val = None
                nilai_str = "-"

            if ujian.metode == Ujian.Metode.PILIHAN_GANDA:
                benar = sum(
                    1
                    for j in pengumpulan.jawaban_pilihan_ganda.all()
                    if j.opsi and j.opsi.is_kunci
                )
                rincian_str = f"{benar}/{total_soal} Benar"
            else:
                rincian_str = f"{total_soal} Soal Esai"
        elif pengumpulan and pengumpulan.started_at:
            submitted_str = "-"
            if pengumpulan.waktu_habis:
                status_str = "Waktu Habis (Belum Submit)"
            else:
                status_str = "Sedang Mengerjakan"
            rincian_str = "-"
            nilai_val = None
            nilai_str = "-"
        else:
            submitted_str = "-"
            status_str = "Belum Mengerjakan"
            rincian_str = "-"
            nilai_val = None
            nilai_str = "-"

        rows.append({
            "no": idx,
            "nama": nama,
            "nip_nrp": nip_nrp,
            "waktu_submit": submitted_str,
            "rincian": rincian_str,
            "status": status_str,
            "nilai": nilai_str,
            "nilai_num": nilai_val,
        })

    avg_score = (sum(scores) / len(scores)) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0

    stats = {
        "total_siswa": len(students),
        "sudah_kumpul": submitted_count,
        "belum_kumpul": len(students) - submitted_count,
        "sudah_dinilai": len(scores),
        "rata_rata": avg_score,
        "tertinggi": max_score,
        "terendah": min_score,
    }

    return {
        "ujian": ujian,
        "total_soal": total_soal,
        "rows": rows,
        "stats": stats,
    }


def generate_exam_excel(ujian: Ujian) -> io.BytesIO:
    """
    Menghasilkan file Excel (.xlsx) rekapitulasi hasil ujian.
    """
    data = get_exam_summary_data(ujian)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hasil Ujian"

    # Styling constants
    green_header = PatternFill(start_color="176B45", end_color="176B45", fill_type="solid")
    green_soft = PatternFill(start_color="E4F2E9", end_color="E4F2E9", fill_type="solid")
    gray_zebra = PatternFill(start_color="F7F9F7", end_color="F7F9F7", fill_type="solid")
    font_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_regular = Font(name="Calibri", size=10)
    font_muted = Font(name="Calibri", size=10, color="555555")

    border_thin = Side(border_style="thin", color="DDE4DF")
    cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # 1. Header Banner
    ws.merge_cells("A1:G1")
    title_cell = ws["A1"]
    title_cell.value = "LMS PRESISI - REKAPITULASI HASIL UJIAN"
    title_cell.font = font_title
    title_cell.fill = green_header
    title_cell.alignment = align_center
    ws.row_dimensions[1].height = 36

    # 2. Metadata Ujian
    mulai_str = timezone.localtime(ujian.waktu_mulai).strftime("%d-%m-%Y %H:%M")
    selesai_str = timezone.localtime(ujian.waktu_selesai).strftime("%d-%m-%Y %H:%M")

    meta_info = [
        ("Judul Ujian", ujian.judul, "Kelas", ujian.kelas.nama_kelas),
        ("Mata Pelajaran", f"{ujian.mapel.nama_mapel} ({ujian.mapel.kode_mapel})", "Kurikulum", str(ujian.mapel.kurikulum)),
        ("Gadik Pengajar", ujian.gadik.display_name, "Metode / Durasi", f"{ujian.get_metode_display()} / {ujian.durasi_menit} Menit"),
        ("Jadwal Ujian", f"{mulai_str} s/d {selesai_str}", "Tanggal Unduh", timezone.localtime(timezone.now()).strftime("%d-%m-%Y %H:%M")),
    ]

    for row_idx, (k1, v1, k2, v2) in enumerate(meta_info, start=3):
        ws.cell(row=row_idx, column=1, value=k1).font = font_bold
        ws.cell(row=row_idx, column=2, value=v1).font = font_regular
        ws.cell(row=row_idx, column=4, value=k2).font = font_bold
        ws.cell(row=row_idx, column=5, value=v2).font = font_regular

    # 3. Table Header
    start_table_row = 8
    headers = ["No", "Nama Siswa", "NIP / NRP", "Waktu Pengumpulan", "Rincian Jawaban", "Status", "Nilai Akhir"]
    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=start_table_row, column=col_idx, value=text)
        cell.font = font_header
        cell.fill = green_header
        cell.alignment = align_center
        cell.border = cell_border
    ws.row_dimensions[start_table_row].height = 26

    # 4. Data Rows
    current_row = start_table_row + 1
    for r in data["rows"]:
        ws.cell(row=current_row, column=1, value=r["no"]).alignment = align_center
        ws.cell(row=current_row, column=2, value=r["nama"]).alignment = align_left
        ws.cell(row=current_row, column=3, value=r["nip_nrp"]).alignment = align_center
        ws.cell(row=current_row, column=4, value=r["waktu_submit"]).alignment = align_center
        ws.cell(row=current_row, column=5, value=r["rincian"]).alignment = align_center
        ws.cell(row=current_row, column=6, value=r["status"]).alignment = align_center
        
        nilai_cell = ws.cell(row=current_row, column=7, value=r["nilai_num"] if r["nilai_num"] is not None else "-")
        nilai_cell.alignment = align_center

        # Borders and zebra
        fill_to_apply = gray_zebra if (r["no"] % 2 == 0) else None
        for col_idx in range(1, 8):
            c = ws.cell(row=current_row, column=col_idx)
            c.border = cell_border
            if col_idx == 7 and r["nilai_num"] is not None:
                c.font = font_bold
                c.number_format = "0.00"
            else:
                c.font = font_regular
            if fill_to_apply:
                c.fill = fill_to_apply

        ws.row_dimensions[current_row].height = 22
        current_row += 1

    # 5. Summary Statistics Box
    current_row += 1
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
    summary_head = ws.cell(row=current_row, column=1, value="RINGKASAN STATISTIK KELAS")
    summary_head.font = font_bold
    summary_head.fill = green_soft
    summary_head.alignment = align_left
    current_row += 1

    stats = data["stats"]
    stat_rows = [
        ("Total Siswa di Kelas", f"{stats['total_siswa']} Siswa", "Nilai Rata-rata", f"{stats['rata_rata']:.2f}"),
        ("Sudah Mengumpulkan", f"{stats['sudah_kumpul']} Siswa", "Nilai Tertinggi", f"{stats['tertinggi']:.2f}"),
        ("Belum Mengumpulkan", f"{stats['belum_kumpul']} Siswa", "Nilai Terendah", f"{stats['terendah']:.2f}"),
    ]
    for k1, v1, k2, v2 in stat_rows:
        ws.cell(row=current_row, column=1, value=k1).font = font_muted
        ws.cell(row=current_row, column=2, value=v1).font = font_bold
        ws.cell(row=current_row, column=4, value=k2).font = font_muted
        ws.cell(row=current_row, column=5, value=v2).font = font_bold
        current_row += 1

    # Auto-adjust column widths
    column_widths = {1: 6, 2: 30, 3: 18, 4: 20, 5: 18, 6: 24, 7: 14}
    for col_idx, width in column_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_exam_pdf(ujian: Ujian) -> io.BytesIO:
    """
    Menghasilkan file PDF (.pdf) rekapitulasi hasil ujian dengan ReportLab.
    """
    data = get_exam_summary_data(ujian)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    color_primary = colors.HexColor("#176B45")
    color_dark = colors.HexColor("#10251C")
    color_muted = colors.HexColor("#68756E")
    color_line = colors.HexColor("#DDE4DF")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=color_primary,
        alignment=1,  # Center
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=color_dark,
        alignment=1,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=color_dark,
    )

    meta_val_style = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=color_dark,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1,
    )

    cell_center_style = ParagraphStyle(
        "CellCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=1,
    )

    cell_left_style = ParagraphStyle(
        "CellLeft",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=0,
    )

    cell_bold_center_style = ParagraphStyle(
        "CellBoldCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        alignment=1,
    )

    story = []

    # 1. Header & Kop
    story.append(Paragraph("LEMBAGA PENDIDIKAN DAN PELATIHAN POLRI", subtitle_style))
    story.append(Paragraph("LMS PRESISI - REKAPITULASI HASIL UJIAN", title_style))
    story.append(Spacer(1, 0.25 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=color_primary, spaceBefore=2, spaceAfter=8))

    # 2. Metadata Grid
    mulai_str = timezone.localtime(ujian.waktu_mulai).strftime("%d/%m/%Y %H:%M")
    selesai_str = timezone.localtime(ujian.waktu_selesai).strftime("%d/%m/%Y %H:%M")
    download_str = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    meta_data = [
        [
            Paragraph("Judul Ujian:", meta_label_style),
            Paragraph(ujian.judul, meta_val_style),
            Paragraph("Kelas:", meta_label_style),
            Paragraph(ujian.kelas.nama_kelas, meta_val_style),
        ],
        [
            Paragraph("Mata Pelajaran:", meta_label_style),
            Paragraph(f"{ujian.mapel.nama_mapel} ({ujian.mapel.kode_mapel})", meta_val_style),
            Paragraph("Kurikulum:", meta_label_style),
            Paragraph(str(ujian.mapel.kurikulum), meta_val_style),
        ],
        [
            Paragraph("Gadik Pengajar:", meta_label_style),
            Paragraph(ujian.gadik.display_name, meta_val_style),
            Paragraph("Metode / Durasi:", meta_label_style),
            Paragraph(f"{ujian.get_metode_display()} / {ujian.durasi_menit} Menit", meta_val_style),
        ],
        [
            Paragraph("Jadwal Ujian:", meta_label_style),
            Paragraph(f"{mulai_str} s/d {selesai_str}", meta_val_style),
            Paragraph("Tanggal Unduh:", meta_label_style),
            Paragraph(download_str, meta_val_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[3.2 * cm, 10.5 * cm, 3.2 * cm, 9.8 * cm])
    meta_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    # 3. Main Data Table
    table_headers = [
        Paragraph("No", table_header_style),
        Paragraph("Nama Siswa", table_header_style),
        Paragraph("NIP / NRP", table_header_style),
        Paragraph("Waktu Submit", table_header_style),
        Paragraph("Rincian", table_header_style),
        Paragraph("Status", table_header_style),
        Paragraph("Nilai", table_header_style),
    ]

    table_rows = [table_headers]

    for r in data["rows"]:
        table_rows.append([
            Paragraph(str(r["no"]), cell_center_style),
            Paragraph(r["nama"], cell_left_style),
            Paragraph(r["nip_nrp"], cell_center_style),
            Paragraph(r["waktu_submit"], cell_center_style),
            Paragraph(r["rincian"], cell_center_style),
            Paragraph(r["status"], cell_center_style),
            Paragraph(r["nilai"], cell_bold_center_style),
        ])

    col_widths = [1.2 * cm, 7.8 * cm, 4.0 * cm, 3.8 * cm, 3.4 * cm, 4.5 * cm, 2.0 * cm]
    main_table = Table(table_rows, colWidths=col_widths, repeatRows=1)

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), color_primary),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, color_line),
    ]

    # Alternate row background
    for i in range(1, len(table_rows)):
        if i % 2 == 0:
            t_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F7F9F7")))

    main_table.setStyle(TableStyle(t_style))
    story.append(main_table)
    story.append(Spacer(1, 0.4 * cm))

    # 4. Summary and Signature Section
    stats = data["stats"]
    stats_text = (
        f"<b>Total Siswa:</b> {stats['total_siswa']} | "
        f"<b>Mengumpulkan:</b> {stats['sudah_kumpul']} | "
        f"<b>Belum:</b> {stats['belum_kumpul']} &nbsp;&nbsp;&nbsp;&nbsp; "
        f"<b>Rata-rata:</b> {stats['rata_rata']:.2f} | "
        f"<b>Tertinggi:</b> {stats['tertinggi']:.2f} | "
        f"<b>Terendah:</b> {stats['terendah']:.2f}"
    )

    summary_p = Paragraph(stats_text, meta_val_style)

    # Signature Block
    today_formatted = timezone.localtime(timezone.now()).strftime("%d %B %Y")
    nip_gadik = ujian.gadik.nip_nrp or "-"
    sig_text = (
        f"<br/>"
        f"Gadik Pengajar,<br/><br/><br/><br/>"
        f"<b><u>{ujian.gadik.display_name}</u></b><br/>"
        f"NIP/NRP: {nip_gadik}"
    )
    sig_p = Paragraph(sig_text, meta_val_style)

    footer_data = [
        [summary_p, sig_p]
    ]
    footer_table = Table(footer_data, colWidths=[17.5 * cm, 9.2 * cm])
    footer_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(footer_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
