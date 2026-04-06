import streamlit as st
from docxtpl import DocxTemplate, RichText
from datetime import datetime, timedelta, timezone, date
import io
import pandas as pd
import os
import tempfile
import zipfile
import subprocess
import shutil

# --- IMPORT PDF (VERSI AMAN) ---
try:
    from pypdf import PdfReader, PdfWriter
    PDF_SUPPORT = True
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        PDF_SUPPORT = True
    except:
        PDF_SUPPORT = False

# --- CONFIG & DATABASE FILE ---
DB_FILE = 'database_lembur.csv'
DOCS_FOLDER = 'generated_docs'

# --- SETUP FOLDER ---
if not os.path.exists(DOCS_FOLDER):
    os.makedirs(DOCS_FOLDER, exist_ok=True)

# --- DATABASE UTAMA (MASTER DATA) ---
master_karyawan = {
    "ANGGA SEPTIAN CAHYA": {"nik": "09244925", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner", "gaji": 5447000},
    "NADINE PUSPITA SARI": {"nik": "09244924", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner", "gaji": 5447000},
    "MOHAMMAD SYAIFUL ICHSAN": {"nik": "09244931", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner", "gaji": 5447000},
    "NAFIRA NURZAHRA": {"nik": "09244914", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner", "gaji": 5447000},
    "MOCH DIKI RAMDANI": {"nik": "09244923", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure", "gaji": 5447000},
    "MUKHLIS": {"nik": "09244929", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure", "gaji": 5447000},
    "AZIS SAEFUDIN": {"nik": "09244926", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure", "gaji": 5447000}
}
data_atasan = {
    "ERWIN SETIAWAN": "82233018",
    "ARIS KURNIAWAN NOOR": "89111077"
}
users_db = {"admin": "admin123", "hrd": "hrd123"}

# --- FUNGSI GITHUB HELPER ---
def get_github_secrets():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        return token, repo
    except:
        return None, None

def push_to_github(file_path, repo_path, commit_message):
    token, repo_name = get_github_secrets()
    if not token or not repo_name:
        return False
    try:
        from github import Github, GithubException
        g = Github(token)
        repo = g.get_repo(repo_name)
        with open(file_path, "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(repo_path)
            repo.update_file(contents.path, commit_message, content, contents.sha, branch="main")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(repo_path, commit_message, content, branch="main")
            else:
                raise e
        return True
    except Exception as e:
        print(f"GitHub Sync Error: {e}")
        return False

# --- FUNGSI DATABASE (CSV) ---
def init_db():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=[
            "Timestamp", "Nama", "NIK", "Bagian", "Lokasi", 
            "Periode_Lembur", "Total_Jam", "Uraian", "Atasan", "FilePath"
        ])
        df.to_csv(DB_FILE, index=False)

def save_to_db(data):
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
    else:
        df = pd.DataFrame(columns=["Timestamp", "Nama", "NIK", "Bagian", "Lokasi", "Periode_Lembur", "Total_Jam", "Uraian", "Atasan", "FilePath"])
    
    new_df = pd.DataFrame([data])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(DB_FILE, index=False)
    push_to_github(DB_FILE, DB_FILE, f"Update DB: {data['Nama']}")

def load_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    try:
        return pd.read_csv(DB_FILE)
    except:
        return pd.DataFrame()

# --- FUNGSI BANTUAN ---
def format_tanggal_satu(tanggal_obj):
    hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    return f"{hari_list[tanggal_obj.weekday()]}, {tanggal_obj.day} {bulan_list[tanggal_obj.month - 1]} {tanggal_obj.year}"

def format_tanpa_hari(tanggal_obj):
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    return f"{tanggal_obj.day} {bulan_list[tanggal_obj.month - 1]} {tanggal_obj.year}"

def format_tanggal_range(tanggal_mulai, tanggal_selesai):
    t1 = format_tanggal_satu(tanggal_mulai)
    t2 = format_tanggal_satu(tanggal_selesai)
    return f"{t1} - {t2}"

def hitung_durasi(mulai_obj, selesai_obj):
    delta = datetime.combine(datetime.min, selesai_obj) - datetime.combine(datetime.min, mulai_obj)
    if delta.total_seconds() < 0: delta += timedelta(days=1)
    total_jam = int(delta.total_seconds() // 3600)
    total_menit = int((delta.total_seconds() % 3600) // 60)
    teks_jam = f"{total_jam} jam"
    if total_menit > 0: teks_jam += f" {total_menit} menit"
    return f"{mulai_obj.strftime('%H:%M')} - {selesai_obj.strftime('%H:%M')} , {teks_jam}", total_jam + (total_menit / 60.0)

def format_td(td):
    total_sec = td.total_seconds()
    if total_sec < 0:
        total_sec = 0
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    if m > 0:
        return f"{h} Jam {m} Menit"
    return f"{h} Jam"

# ============ FUNGSI KALKULATOR GAJI ============
def get_upah_per_jam(gaji):
    return gaji / 173

def get_eff_jam(jam):
    """Potong 1 jam tiap kelipatan 5 (istirahat)"""
    return jam - (jam // 5)

def calc_weekday(eff_jam, up_per_jam):
    """Rumus Weekday berdasarkan PP 35/2021"""
    total = 0
    if eff_jam >= 1:
        total += 1.5 * up_per_jam
    if eff_jam >= 2:
        jam2_8 = min(eff_jam - 1, 7)
        total += jam2_8 * 2 * up_per_jam
    if eff_jam >= 9:
        total += 1 * 3 * up_per_jam
    if eff_jam >= 10:
        total += (eff_jam - 9) * 4 * up_per_jam
    return round(total)

def calc_weekend(eff_jam, up_per_jam):
    """Rumus Weekend"""
    total = 0
    if eff_jam <= 8:
        total = eff_jam * 2 * up_per_jam
    elif eff_jam == 9:
        total = (8 * 2 * up_per_jam) + (1 * 3 * up_per_jam)
    else:
        total = (8 * 2 * up_per_jam) + (1 * 3 * up_per_jam) + ((eff_jam - 9) * 4 * up_per_jam)
    return round(total)

# --- DATA LIBUR NASIONAL INDONESIA 2025-2026 ---
LIBUR_NASIONAL = {
    "2025-01-01": "Tahun Baru Masehi",
    "2025-03-29": "Hari Raya Nyepi",
    "2025-03-31": "Idul Fitri 1446 H",
    "2025-04-01": "Idul Fitri 1446 H",
    "2025-05-01": "Hari Buruh",
    "2025-05-12": "Hari Raya Waisak",
    "2025-05-29": "Kenaikan Yesus Kristus",
    "2025-06-01": "Hari Lahir Pancasila",
    "2025-06-27": "Idul Adha 1446 H",
    "2025-07-17": "Tahun Baru Islam 1447 H",
    "2025-08-17": "HUT Kemerdekaan RI",
    "2025-09-05": "Maulid Nabi Muhammad SAW",
    "2025-12-25": "Hari Raya Natal",
    "2026-01-01": "Tahun Baru Masehi",
    "2026-03-19": "Hari Raya Nyepi",
    "2026-03-20": "Idul Fitri 1447 H",
    "2026-03-21": "Idul Fitri 1447 H",
    "2026-05-01": "Hari Buruh",
    "2026-05-04": "Hari Raya Waisak",
    "2026-05-14": "Kenaikan Yesus Kristus",
    "2026-06-01": "Hari Lahir Pancasila",
    "2026-06-17": "Idul Adha 1447 H",
    "2026-07-07": "Tahun Baru Islam 1448 H",
    "2026-08-17": "HUT Kemerdekaan RI",
    "2026-08-25": "Maulid Nabi Muhammad SAW",
    "2026-12-25": "Hari Raya Natal",
}

# --- CUTI BERSAMA 2025-2026 ---
CUTI_BERSAMA = {
    "2025-03-28": "Cuti Bersama Nyepi",
    "2025-04-02": "Cuti Bersama Idul Fitri",
    "2025-04-03": "Cuti Bersama Idul Fitri",
    "2025-04-04": "Cuti Bersama Idul Fitri",
    "2025-04-07": "Cuti Bersama Idul Fitri",
    "2025-05-13": "Cuti Bersama Waisak",
    "2025-06-30": "Cuti Bersama Idul Adha",
    "2025-12-26": "Cuti Bersama Natal",
    "2026-03-18": "Cuti Bersama Nyepi",
    "2026-03-22": "Cuti Bersama Idul Fitri",
    "2026-03-23": "Cuti Bersama Idul Fitri",
    "2026-03-24": "Cuti Bersama Idul Fitri",
    "2026-12-28": "Cuti Bersama Natal",
}

def cek_tipe_hari(tgl_obj):
    """Cek tipe hari: Weekday, Weekend, atau Libur Nasional/Cuti Bersama"""
    tgl_str = tgl_obj.strftime("%Y-%m-%d")
    
    if tgl_str in LIBUR_NASIONAL:
        return f"Libur Nasional ({LIBUR_NASIONAL[tgl_str]})"
    
    if tgl_str in CUTI_BERSAMA:
        return f"Cuti Bersama ({CUTI_BERSAMA[tgl_str]})"
    
    day = tgl_obj.weekday()
    if day >= 5:
        return "Weekend"
    
    return "Hari Kerja"

# --- FITUR KALKULATOR GAJI DAN LEMBUR ---
def show_gaji_calculator():
    st.title("💰 Kalkulator Gaji & Lembur")
    st.markdown("---")
    
    if 'data_lembur' not in st.session_state:
        st.session_state.data_lembur = []
    
    col1, col2 = st.columns(2)
    with col1:
        gaji_pokok = st.number_input("Gaji Pokok", min_value=0, value=5447000, step=100000, format="%d")
    with col2:
        st.metric("Upah per Jam", f"Rp {get_upah_per_jam(gaji_pokok):,.0f}")
    
    st.markdown("---")
    st.subheader("📝 Input Data Lembur")
    
    col_tgl1, col_tgl2 = st.columns(2)
    with col_tgl1:
        tgl_mulai = st.date_input("Tanggal Mulai", value=date.today())
    with col_tgl2:
        tgl_selesai = st.date_input("Tanggal Selesai", value=date.today())
    
    col_jam1, col_jam2 = st.columns(2)
    with col_jam1:
        jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
    with col_jam2:
        jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("22:00", "%H:%M").time())
    
    col_add, col_space = st.columns([1, 3])
    with col_add:
        if st.button("➕ TAMBAH DATA LEMBUR", type="primary", use_container_width=True):
            d1 = datetime.combine(tgl_mulai, jam_mulai)
            d2 = datetime.combine(tgl_selesai, jam_selesai)
            
            if d2 <= d1:
                d2 += timedelta(days=1)
            
            current = d1
            added_count = 0
            
            while current < d2:
                end_of_day = current.replace(hour=23, minute=59, second=59, microsecond=999999)
                segment_end = min(d2, end_of_day)
                
                hours = (segment_end - current).total_seconds() / 3600
                exact_hours = hours
                
                tipe = cek_tipe_hari(current)
                is_weekend = ("Libur" in tipe or "Cuti" in tipe or "Weekend" in tipe)
                
                st.session_state.data_lembur.append({
                    "tanggal": current.strftime("%Y-%m-%d"),
                    "tipe": tipe,
                    "raw_jam": exact_hours,
                    "is_weekend": is_weekend
                })
                
                added_count += 1
                current = (end_of_day + timedelta(seconds=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            
            st.success(f"✅ Berhasil menambahkan {added_count} data lembur!")
            st.rerun()
    
    st.markdown("---")
    st.subheader("📋 Data Lembur")
    
    if st.session_state.data_lembur:
        table_data = []
        for i, d in enumerate(st.session_state.data_lembur):
            eff_jam = get_eff_jam(int(d['raw_jam']))
            up_per_jam = get_upah_per_jam(gaji_pokok)
            if d['is_weekend']:
                upah = calc_weekend(eff_jam, up_per_jam)
            else:
                upah = calc_weekday(eff_jam, up_per_jam)
            
            table_data.append({
                "Pilih": False,
                "No": i + 1,
                "Tanggal": d['tanggal'],
                "Tipe": d['tipe'],
                "Raw Jam": f"{d['raw_jam']:.1f}",
                "Eff Jam": eff_jam,
                "Upah": f"Rp {upah:,.0f}"
            })
        
        df_display = pd.DataFrame(table_data)
        
        edited_df = st.data_editor(
            df_display,
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                "No": st.column_config.NumberColumn("No", disabled=True),
                "Tanggal": st.column_config.TextColumn("Tanggal", disabled=True),
                "Tipe": st.column_config.TextColumn("Tipe", disabled=True),
                "Raw Jam": st.column_config.TextColumn("Raw Jam", disabled=True),
                "Eff Jam": st.column_config.NumberColumn("Eff Jam", disabled=True),
                "Upah": st.column_config.TextColumn("Upah", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="data_editor_lembur"
        )
        
        col_del1, col_del2, col_del3 = st.columns([1, 1, 2])
        
        with col_del1:
            if st.button("🗑️ Hapus yang Dipilih", type="secondary", use_container_width=True):
                selected_indices = [i for i, row in edited_df.iterrows() if row['Pilih']]
                if selected_indices:
                    for idx in sorted(selected_indices, reverse=True):
                        st.session_state.data_lembur.pop(idx)
                    st.success(f"✅ Berhasil menghapus {len(selected_indices)} data!")
                    st.rerun()
                else:
                    st.warning("Pilih data yang mau dihapus dulu!")
        
        with col_del2:
            if st.button("🗑️ Hapus Semua Data", type="secondary", use_container_width=True):
                st.session_state.data_lembur = []
                st.rerun()
    else:
        st.info("Belum ada data lembur. Silakan tambah data di atas.")
    
    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("💰 HITUNG GAJI", type="primary", use_container_width=True):
            if not st.session_state.data_lembur:
                st.warning("Belum ada data lembur!")
            else:
                total_lembur = 0
                log_text = "============ LOG PERHITUNGAN ============\n\n"
                
                for d in st.session_state.data_lembur:
                    eff_jam = get_eff_jam(int(d['raw_jam']))
                    up_per_jam = get_upah_per_jam(gaji_pokok)
                    if d['is_weekend']:
                        upah = calc_weekend(eff_jam, up_per_jam)
                    else:
                        upah = calc_weekday(eff_jam, up_per_jam)
                    
                    total_lembur += upah
                    log_text += f"Tanggal: {d['tanggal']} [{d['tipe']}]\n"
                    log_text += f"  Raw: {d['raw_jam']:.1f} jam -> Eff: {eff_jam} jam\n"
                    log_text += f"  Upah: Rp {upah:,.0f}\n"
                    log_text += "------------------------------------------\n"
                
                bpjs_kes = round(gaji_pokok * 0.01)
                bpjs_jht = round(gaji_pokok * 0.02)
                bpjs_jp = round(gaji_pokok * 0.01)
                total_bpjs = bpjs_kes + bpjs_jht + bpjs_jp
                
                netto = gaji_pokok + total_lembur - total_bpjs
                
                log_text += f"\n=== POTONGAN BPJS ===\n"
                log_text += f"BPJS Kesehatan (1%): Rp {bpjs_kes:,.0f}\n"
                log_text += f"BPJS JHT (2%): Rp {bpjs_jht:,.0f}\n"
                log_text += f"BPJS JP (1%): Rp {bpjs_jp:,.0f}\n"
                log_text += f"Total Potongan: Rp {total_bpjs:,.0f}\n\n"
                log_text += f"=== RINGKASAN ===\n"
                log_text += f"Gaji Pokok: Rp {gaji_pokok:,.0f}\n"
                log_text += f"Total Lembur: Rp {total_lembur:,.0f}\n"
                log_text += f"Total BPJS: Rp {total_bpjs:,.0f}\n"
                log_text += f"Gaji Bersih: Rp {netto:,.0f}\n"
                
                # TAMPILAN HASIL 1 KOLOM TAPI RAPI (PAKE EXPANDER BIAR GAK KEPOTONG)
                st.markdown("---")
                st.subheader("📊 Hasil Perhitungan")
                
                # Pakai container dengan border biar rapi
                with st.container(border=True):
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        st.markdown("### 💰 Gaji Pokok")
                        st.markdown(f"<h2 style='color:#2ecc71;'>Rp {gaji_pokok:,.0f}</h2>", unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown("### 📊 Total BPJS")
                        st.markdown(f"<h3 style='color:#e74c3c;'>Rp {total_bpjs:,.0f}</h3>", unsafe_allow_html=True)
                        st.caption("BPJS Kes 1% + JHT 2% + JP 1%")
                    
                    with col_r2:
                        st.markdown("### ⏱️ Total Lembur")
                        st.markdown(f"<h2 style='color:#3498db;'>Rp {total_lembur:,.0f}</h2>", unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown("### 💵 POTONGAN")
                        st.markdown(f"<h3 style='color:#e67e22;'>Rp {total_bpjs:,.0f}</h3>", unsafe_allow_html=True)
                        st.caption("Total potongan BPJS")
                
                st.markdown("---")
                st.success(f"**💰 TOTAL GAJI BERSIH: Rp {netto:,.0f}**")
                
                with st.expander("📝 Lihat Detail Log"):
                    st.code(log_text, language="text")
    
    with col_btn2:
        if st.button("📥 EXPORT CSV", use_container_width=True):
            if not st.session_state.data_lembur:
                st.warning("Tidak ada data untuk diexport!")
            else:
                csv_data = []
                for d in st.session_state.data_lembur:
                    eff_jam = get_eff_jam(int(d['raw_jam']))
                    up_per_jam = get_upah_per_jam(gaji_pokok)
                    if d['is_weekend']:
                        upah = calc_weekend(eff_jam, up_per_jam)
                    else:
                        upah = calc_weekday(eff_jam, up_per_jam)
                    
                    csv_data.append({
                        "Tanggal": d['tanggal'],
                        "Tipe": d['tipe'],
                        "Raw Jam": d['raw_jam'],
                        "Jam Efektif": eff_jam,
                        "Upah": upah
                    })
                
                df_csv = pd.DataFrame(csv_data)
                csv_buffer = io.BytesIO()
                df_csv.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_buffer,
                    file_name=f"gaji_lembur_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="export_csv_btn"
                )

# --- FUNGSI TOOLS PDF ---
def show_pdf_tools():
    st.title("🛠️ Tools PDF & File")
    st.markdown("---")
    tab1, tab2 = st.tabs(["📑 Merge PDF", "📝 Word to PDF"])

    with tab1:
        st.subheader("Gabungkan File PDF")
        if not PDF_SUPPORT: st.error("Library PDF tidak ditemukan.")
        else:
            if 'pdf_merge_list' not in st.session_state: st.session_state['pdf_merge_list'] = []
            uploaded_pdfs = st.file_uploader("Pilih beberapa file PDF", type="pdf", accept_multiple_files=True, key="merge_pdf_uploader_widget")
            
            if uploaded_pdfs:
                uploader_names = {f.name for f in uploaded_pdfs}
                stored_names = {f.name for f in st.session_state['pdf_merge_list']}
                new_files = [f for f in uploaded_pdfs if f.name not in stored_names]
                if new_files: st.session_state['pdf_merge_list'].extend(new_files)
                st.session_state['pdf_merge_list'] = [f for f in st.session_state['pdf_merge_list'] if f.name in uploader_names]
            else: st.session_state['pdf_merge_list'] = []

            if st.session_state['pdf_merge_list']:
                st.info("🔄 Atur urutan file:")
                for i, pdf_file in enumerate(st.session_state['pdf_merge_list']):
                    col_name, col_up, col_down = st.columns([6, 1, 1])
                    with col_name: st.markdown(f"**{i+1}.** {pdf_file.name}")
                    with col_up:
                        if st.button("⬆️", key=f"up_{i}", disabled=(i == 0)):
                            items = st.session_state['pdf_merge_list']; items[i], items[i-1] = items[i-1], items[i]; st.rerun()
                    with col_down:
                        if st.button("⬇️", key=f"down_{i}", disabled=(i == len(st.session_state['pdf_merge_list']) - 1)):
                            items = st.session_state['pdf_merge_list']; items[i], items[i+1] = items[i+1], items[i]; st.rerun()
                
                if st.button("Gabungkan PDF", type="primary"):
                    try:
                        writer = PdfWriter()
                        for pdf in st.session_state['pdf_merge_list']:
                            pdf.seek(0); reader = PdfReader(pdf)
                            for page in reader.pages: writer.add_page(page)
                        buffer = io.BytesIO(); writer.write(buffer); buffer.seek(0)
                        st.success("Berhasil digabung!")
                        st.download_button("📥 Download Hasil", data=buffer, file_name="merged_document.pdf", mime="application/pdf")
                    except Exception as e: st.error(f"Error: {e}")

    with tab2:
        st.subheader("Convert Word ke PDF")
        st.info("ℹ️ Menggunakan LibreOffice untuk hasil akurat.")
        libreoffice_exists = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice_exists: st.error("❌ LibreOffice tidak ditemukan.")
        
        uploaded_docxs = st.file_uploader("Pilih file Word (.docx)", type="docx", accept_multiple_files=True, key="word_to_pdf_uploader")
        if uploaded_docxs and st.button("Convert Semua ke PDF", type="primary"):
            if not libreoffice_exists: st.error("Gagal.")
            else:
                try:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        progress_bar = st.progress(0)
                        with tempfile.TemporaryDirectory() as temp_dir:
                            for i, docx_file in enumerate(uploaded_docxs):
                                input_path = os.path.join(temp_dir, f"temp_{i}.docx")
                                with open(input_path, "wb") as f: f.write(docx_file.getbuffer())
                                subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp_dir, input_path], capture_output=True)
                                output_pdf = os.path.join(temp_dir, f"temp_{i}.pdf")
                                if os.path.exists(output_pdf):
                                    with open(output_pdf, "rb") as pdf_file: zf.writestr(f"{os.path.splitext(docx_file.name)[0]}.pdf", pdf_file.read())
                                progress_bar.progress((i + 1) / len(uploaded_docxs))
                    zip_buffer.seek(0)
                    st.success("Berhasil convert!")
                    st.download_button("📥 Download ZIP", data=zip_buffer, file_name="converted_docs.zip", mime="application/zip")
                except Exception as e: st.error(f"Error: {e}")

# --- FITUR KALKULATOR LEMBUR (TAMPILAN SIMPLE) ---
def show_overtime_calculator():
    st.title("⏱️ Input Durasi Lembur")
    st.markdown("---")
    st.markdown("Isi data dibawah ini untuk menghitung durasi lembur otomatis.")
    
    col_date, col_weekend = st.columns([2, 1])
    with col_date: 
        tgl_lembur = st.date_input("Tanggal Lembur", value=date.today())
    with col_weekend: 
        is_weekend = st.checkbox("Weekend / Holiday (CASE 4)", value=False)

    st.markdown("#### 🕒 Jadwal Shift (System)")
    col_sched1, col_sched2 = st.columns(2)
    with col_sched1: 
        sched_in = st.time_input("Mulai Shift (System)", value=datetime.strptime("08:30", "%H:%M").time())
    with col_sched2: 
        sched_out = st.time_input("Pulang Shift (System)", value=datetime.strptime("17:30", "%H:%M").time())

    st.markdown("#### ⚡ Jadwal Lembur Aktual")
    col_ot1, col_ot2 = st.columns(2)
    with col_ot1: 
        ot_in = st.time_input("Mulai Lembur", value=datetime.strptime("22:00", "%H:%M").time())
    with col_ot2: 
        ot_out = st.time_input("Selesai Lembur", value=datetime.strptime("04:00", "%H:%M").time())

    if st.button("Hitung Durasi (SUBMIT)", type="primary"):
        dt_sched_in = datetime.combine(tgl_lembur, sched_in)
        dt_sched_out = datetime.combine(tgl_lembur, sched_out)
        dt_ot_in = datetime.combine(tgl_lembur, ot_in)
        dt_ot_out = datetime.combine(tgl_lembur, ot_out)
        
        if dt_ot_out <= dt_ot_in:
            dt_ot_out += timedelta(days=1)
        
        if dt_sched_out <= dt_sched_in:
            dt_sched_out += timedelta(days=1)
        
        overtime_before = timedelta()
        overtime_after = timedelta()
        break_before = timedelta()
        break_after = timedelta()
        case_name = "UNKNOWN"
        
        if is_weekend:
            case_name = "CASE 4: Lembur di Hari Libur / Weekend"
            total_duration = dt_ot_out - dt_ot_in
            overtime_after = total_duration
            
        else:
            if dt_ot_in >= dt_sched_out and dt_ot_out <= dt_sched_in + timedelta(days=1):
                case_name = f"CASE 3: Lembur Sebelum Jam Kerja (Overnight)"
                break_after = dt_ot_in - dt_sched_out
                overtime_after = dt_ot_out - dt_sched_out
                total_duration = dt_ot_out - dt_ot_in
                
            elif dt_ot_in >= dt_sched_out and dt_ot_out <= dt_sched_in:
                case_name = f"CASE 2: Lembur Setelah Jam Kerja (Dimulai Setelah {sched_out.strftime('%H:%M')})"
                break_after = dt_ot_in - dt_sched_out
                overtime_after = dt_ot_out - dt_ot_in
                total_duration = overtime_after
                
            elif dt_ot_in < dt_sched_out and dt_ot_out > dt_sched_out:
                case_name = f"CASE 1: Lembur Setelah Jam Kerja (Dimulai Sebelum {sched_out.strftime('%H:%M')})"
                overtime_before = dt_sched_out - dt_ot_in
                overtime_after = dt_ot_out - dt_sched_out
                total_duration = overtime_before + overtime_after
                
            elif dt_ot_out <= dt_sched_in:
                case_name = f"CASE: Lembur Sebelum Jam Kerja (Dini Hari)"
                overtime_before = dt_ot_out - dt_ot_in
                total_duration = overtime_before
                
            else:
                total_duration = dt_ot_out - dt_ot_in
                case_name = "CASE: Lembur Normal"
        
        if total_duration.total_seconds() < 0:
            total_duration = timedelta()
        
        st.markdown("---")
        st.subheader("📊 Hasil Perhitungan")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Overtime Before Duration", format_td(overtime_before))
            st.metric("Break Before Duration", format_td(break_before))
        
        with col2:
            st.metric("Overtime After Duration", format_td(overtime_after))
            st.metric("Break After Duration", format_td(break_after))
        
        st.markdown("---")
        st.success(f"**TOTAL LEMBUR: {format_td(total_duration)}**")
        st.caption(f"Kategori: {case_name}")

# --- HALAMAN LOGIN ---
def show_login_page():
    st.title("🔒 Login Sistem Lembur")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Login Admin", use_container_width=True):
                if username in users_db and users_db[username] == password:
                    st.session_state.logged_in = True; st.session_state.role = "Admin"; st.session_state.username = username; st.rerun()
                else: st.error("Username atau Password salah!")
        with col_btn2:
            if st.button("Login as Guest", use_container_width=True):
                st.session_state.logged_in = True; st.session_state.role = "Guest"; st.session_state.username = "Guest"; st.rerun()

# --- HALAMAN GUEST ---
def show_guest_view():
    st.title("👥 Rekap & Download Lembur")
    st.markdown("---")
    df = load_db()
    if df.empty:
        st.info("Belum ada data lembur yang tercatat.")
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Timestamp'] = df['Timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    list_bulan = df['Bulan'].unique()
    pilih_bulan = st.selectbox("Pilih Bulan", list_bulan)
    
    df_filtered_month = df[df['Bulan'] == pilih_bulan]
    list_nama = df_filtered_month['Nama'].unique()
    pilih_nama = st.selectbox("Pilih Karyawan", ["Semua"] + list(list_nama))

    if pilih_nama == "Semua": 
        df_show = df_filtered_month
    else: 
        df_show = df_filtered_month[df_filtered_month['Nama'] == pilih_nama]

    st.markdown("---")
    if not df_show.empty:
        total_jam = df_show['Total_Jam'].sum()
        jam_bulat = int(total_jam)
        menit_bulat = int((total_jam - jam_bulat) * 60)
        if menit_bulat > 0:
            total_jam_text = f"{jam_bulat} Jam {menit_bulat} Menit"
        else:
            total_jam_text = f"{jam_bulat} Jam"
        st.metric(f"Total Jam Lembur", total_jam_text)
        st.markdown("---")
        for i, row in df_show.iterrows():
            with st.container():
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    jam_val = row['Total_Jam']
                    jam_int = int(jam_val)
                    menit_int = int((jam_val - jam_int) * 60)
                    if menit_int > 0:
                        durasi_text = f"{jam_int} Jam {menit_int} Menit"
                    else:
                        durasi_text = f"{jam_int} Jam"
                    st.write(f"**{row['Nama']}** | {row['Periode_Lembur']}")
                    st.caption(f"Durasi: {durasi_text} | Lokasi: {row['Lokasi']}")
                with col_btn:
                    file_path = row['FilePath']
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as fp:
                            st.download_button(
                                label="📥 Download", data=fp, file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{i}"
                            )
                    else: st.warning("File hilang")
                st.markdown("---")

# --- HALAMAN ADMIN ---
def show_admin_view():
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username}")
        menu = st.radio("Navigation", ["Create Surat", "Dashboard", "Data & Hapus", "Tools PDF", "Input Durasi Lembur", "Kalkulator Gaji dan Lembur"])
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    if menu == "Create Surat": show_form_content()
    elif menu == "Dashboard": show_dashboard()
    elif menu == "Data & Hapus": show_data_management()
    elif menu == "Tools PDF": show_pdf_tools()
    elif menu == "Input Durasi Lembur": show_overtime_calculator()
    elif menu == "Kalkulator Gaji dan Lembur": show_gaji_calculator()

# --- SUB-MENU ADMIN: FORM ---
def show_form_content():
    st.title("📄 Form Surat Tugas Lembur")
    st.markdown("---")
    
    pilih_nama = st.selectbox("Pilih Nama Karyawan", list(master_karyawan.keys()))
    detail = master_karyawan[pilih_nama]
    
    st.text_input("NIK (Otomatis)", value=detail['nik'], disabled=True)
    st.subheader("Data Atasan")
    st.text_input("Atasan (Otomatis)", value=detail['atasan'], disabled=True)
    st.text_input("NIK Atasan", value=data_atasan[detail['atasan']], disabled=True)
    
    st.markdown("---")
    st.subheader("Detail Lembur")
    col1, col2 = st.columns(2)
    with col1:
        idx_bagian = ["IT Business Partner", "IT Infrastructure"].index(detail['bagian'])
        st.selectbox("Bagian/Divisi", ["IT Business Partner", "IT Infrastructure"], index=idx_bagian, disabled=True)
        tanggal_range = st.date_input("Periode Lembur", value=(datetime.today(), datetime.today()))
    with col2:
        lokasi = st.selectbox("Lokasi Kerja", ["Remote (Work From Home)", "Arcadia", "TB. Simatupang"])
        jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
        jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("21:00", "%H:%M").time())

    uraian = st.text_area("Uraian Tugas / Pelaksanaan Lembur", height=100)

    if st.button("Generate & Save", type="primary"):
        try:
            tgl_mulai = tanggal_range[0] if isinstance(tanggal_range, tuple) else tanggal_range
            tgl_selesai = tanggal_range[1] if isinstance(tanggal_range, tuple) and len(tanggal_range)>1 else tanggal_range
            
            doc = DocxTemplate("template_surat.docx")
            tanggal_rapi = format_tanggal_range(tgl_mulai, tgl_selesai)
            durasi_text, durasi_jam = hitung_durasi(jam_mulai, jam_selesai)
            
            context = {
                'nama': pilih_nama, 'nik': detail['nik'], 'bagian': detail['bagian'], 'lokasi': lokasi,
                'hari_tanggal': tanggal_rapi, 'durasi': durasi_text, 'pelaksanaan_lembur': RichText(uraian, bold=True),
                'namabos': detail['atasan'], 'nikbos': data_atasan[detail['atasan']], 'tglacc': format_tanpa_hari(datetime.now())
            }
            doc.render(context)
            
            filename = f"SuratLembur_{pilih_nama.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            file_path = os.path.join(DOCS_FOLDER, filename)
            doc.save(file_path)
            
            repo_file_path = f"{DOCS_FOLDER}/{filename}"
            push_success = push_to_github(file_path, repo_file_path, f"Add Surat: {pilih_nama}")
            
            if push_success:
                st.toast("☁️ File berhasil di-backup ke GitHub!", icon="✅")
            else:
                st.toast("⚠️ File hanya tersimpan lokal (Gagal sync ke GitHub).", icon="⚠️")

            now_jakarta = datetime.now(timezone(timedelta(hours=7)))
            
            save_to_db({
                "Timestamp": now_jakarta.strftime("%Y-%m-%d %H:%M:%S"), "Nama": pilih_nama, "NIK": detail['nik'],
                "Bagian": detail['bagian'], "Lokasi": lokasi, "Periode_Lembur": tanggal_rapi, "Total_Jam": durasi_jam,
                "Uraian": uraian, "Atasan": detail['atasan'], "FilePath": file_path
            })
            
            buffer = io.BytesIO(); doc.save(buffer); buffer.seek(0)
            st.success("Data Tersimpan! 🎉")
            st.download_button("📥 Download", data=buffer, file_name=filename)
        except Exception as e: st.error(f"Error: {e}")

# --- SUB-MENU ADMIN: DASHBOARD ---
def show_dashboard():
    st.title("📊 Dashboard Rekap Lembur")
    df = load_db()
    if df.empty: st.warning("Data masih kosong."); return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Timestamp'] = df['Timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    pilih_bulan = st.selectbox("Pilih Bulan", df['Bulan'].unique())
    df_filtered = df[df['Bulan'] == pilih_bulan]
    
    st.markdown("---")
    st.subheader("Rekap Per Karyawan")
    
    rekap = df_filtered.groupby('Nama')['Total_Jam'].sum().reset_index()

    for i, row in rekap.iterrows():
        with st.container():
            col_nama, col_jam, col_aksi = st.columns([2, 1, 1])
            col_nama.write(f"**{row['Nama']}**")
            jam_val = row['Total_Jam']
            jam_int = int(jam_val)
            menit_int = int((jam_val - jam_int) * 60)
            if menit_int > 0:
                jam_text = f"{jam_int} Jam {menit_int} Menit"
            else:
                jam_text = f"{jam_int} Jam"
            col_jam.metric("Jam", jam_text)
            
            files_person = df_filtered[df_filtered['Nama'] == row['Nama']]
            
            with col_aksi:
                with st.expander("Detail"):
                    if not files_person.empty:
                        for x, data_row in files_person.iterrows():
                            jam_item = data_row['Total_Jam']
                            jam_i = int(jam_item)
                            menit_i = int((jam_item - jam_i) * 60)
                            if menit_i > 0:
                                dur_item = f"{jam_i} Jam {menit_i} Menit"
                            else:
                                dur_item = f"{jam_i} Jam"
                            st.write(f"Tgl: {data_row['Periode_Lembur']} ({dur_item})")
                            file_p = data_row['FilePath']
                            if os.path.exists(file_p):
                                with open(file_p, "rb") as fp:
                                    st.download_button(
                                        label="Download Surat", data=fp, file_name=os.path.basename(file_p),
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dash_dl_{x}"
                                    )
                            else:
                                st.caption("File tidak ditemukan")
        st.markdown("---")

# --- SUB-MENU ADMIN: DATA & HAPUS ---
def show_data_management():
    st.title("⚙️ Manajemen Data Lembur")
    df = load_db()
    if df.empty: st.info("Tidak ada data."); return
    
    df_display = df.copy()
    df_display['Timestamp'] = pd.to_datetime(df_display['Timestamp'])
    df_display['Timestamp'] = df_display['Timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
    
    st.subheader("Data Lengkap")
    st.dataframe(df_display, use_container_width=True)
    st.markdown("---")
    
    st.subheader("Hapus Data")
    list_timestamp = df['Timestamp'].tolist()
    selected_ts = st.selectbox("Pilih Data (Waktu)", list_timestamp)
    if st.button("Hapus Data Terpilih", type="secondary"):
        row_to_delete = df[df['Timestamp'] == selected_ts]
        if not row_to_delete.empty:
            file_to_delete = row_to_delete['FilePath'].values[0]
            if os.path.exists(file_to_delete):
                try: os.remove(file_to_delete)
                except: pass
            df_baru = df[df['Timestamp'] != selected_ts]
            df_baru.to_csv(DB_FILE, index=False)
            push_to_github(DB_FILE, DB_FILE, f"Delete data: {selected_ts}")
            st.success("Data berhasil dihapus!")
            st.rerun()
    
    st.markdown("---")
    
    st.subheader("Cloud Backup")
    token, repo = get_github_secrets()
    if token and repo:
        st.success(f"✅ GitHub Terhubung: {repo}")
        if st.button("☁️ Sync Database ke GitHub (Manual)", type="primary"):
            with st.spinner("Mengupload..."):
                if push_to_github(DB_FILE, DB_FILE, "Manual DB Sync"):
                    st.success("✅ Sync sukses!")
                else:
                    st.error("❌ Gagal sync.")
    else:
        st.error("❌ Secrets belum dissetting.")

# --- MAIN LOGIC ---
def main():
    init_db()
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: show_login_page()
    else:
        if st.session_state.role == "Admin": show_admin_view()
        else:
            with st.sidebar:
                st.title("Menu Guest")
                guest_menu = st.radio("Navigation", ["Rekap Lembur", "Tools PDF", "Input Durasi Lembur", "Kalkulator Gaji dan Lembur"])
                if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
            
            if guest_menu == "Rekap Lembur": show_guest_view()
            elif guest_menu == "Tools PDF": show_pdf_tools()
            elif guest_menu == "Input Durasi Lembur": show_overtime_calculator()
            elif guest_menu == "Kalkulator Gaji dan Lembur": show_gaji_calculator()

if __name__ == "__main__":
    main()
