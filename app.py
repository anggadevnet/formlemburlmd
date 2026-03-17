import streamlit as st
from docxtpl import DocxTemplate, RichText
from datetime import datetime, timedelta, timezone, time, date
import io
import pandas as pd
import os
import tempfile
import zipfile
import platform
import subprocess

# --- IMPORT PDF (VERSI AMAN) ---
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except:
        pass

# --- CONFIG & DATABASE FILE ---
DB_FILE = 'database_lembur.csv'
DOCS_FOLDER = 'generated_docs'

# --- SETUP FOLDER ---
if not os.path.exists(DOCS_FOLDER):
    os.makedirs(DOCS_FOLDER)

# --- DATABASE KARYAWAN & ATASAN ---
data_karyawan = {
    "ANGGA SEPTIAN CAHYA": "092a44925",
    "AZIS SAEFUDIN": "09244926",
    "NADINE PUSPITA SARI": "09244924",
    "MOCH DIKI RAMDANI": "09244923",
    "MOHAMMAD SYAIFUL ICHSAN": "09244931",
    "MUKHLIS": "09244929"
}

data_atasan = {
    "ERWIN SETIAWAN": "82233018",
    "ARIS KURNIAWAN NOOR": "89111077"
}

users_db = {
    "admin": "admin123",
    "hrd": "hrd123"
}

# --- FUNGSI DATABASE (CSV) ---
def init_db():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=[
            "Timestamp", "Nama", "NIK", "Bagian", "Lokasi", 
            "Periode_Lembur", "Total_Jam", "Uraian", "Atasan", "FilePath"
        ])
        df.to_csv(DB_FILE, index=False)

def save_to_db(data):
    df = pd.read_csv(DB_FILE)
    new_df = pd.DataFrame([data])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def load_db():
    df = pd.read_csv(DB_FILE)
    return df

# --- FUNGSI BANTUAN ---
def format_tanggal_satu(tanggal_obj):
    hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    hari = hari_list[tanggal_obj.weekday()]
    bulan = bulan_list[tanggal_obj.month - 1]
    return f"{hari}, {tanggal_obj.day} {bulan} {tanggal_obj.year}"

def format_tanpa_hari(tanggal_obj):
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    bulan = bulan_list[tanggal_obj.month - 1]
    return f"{tanggal_obj.day} {bulan} {tanggal_obj.year}"

def format_tanggal_range(tanggal_mulai, tanggal_selesai):
    t1 = format_tanggal_satu(tanggal_mulai)
    t2 = format_tanggal_satu(tanggal_selesai)
    return f"{t1} - {t2}"

def hitung_durasi(mulai_obj, selesai_obj):
    delta = datetime.combine(datetime.min, selesai_obj) - datetime.combine(datetime.min, mulai_obj)
    if delta.total_seconds() < 0:
        delta = delta + timedelta(days=1)
    total_jam = int(delta.total_seconds() // 3600)
    total_menit = int((delta.total_seconds() % 3600) // 60)
    teks_jam = f"{total_jam} jam"
    if total_menit > 0:
        teks_jam += f" {total_menit} menit"
    mulai_str = mulai_obj.strftime("%H:%M")
    selesai_str = selesai_obj.strftime("%H:%M")
    return f"{mulai_str} - {selesai_str} , {teks_jam}", total_jam

# --- FITUR: KALKULATOR LEMBUR ---
def show_overtime_calculator():
    st.title("⏱️ Kalkulator Durasi Lembur")
    st.markdown("---")
    st.markdown("Isi data dibawah ini untuk menghitung durasi lembur otomatis mengikuti guide logic.")
    
    # --- INPUTS ---
    col_date, col_weekend = st.columns([2, 1])
    with col_date:
        tgl_lembur = st.date_input("Tanggal Lembur", value=date.today())
    with col_weekend:
        is_weekend = st.checkbox("Weekend / Holiday (CASE 4)", value=False)

    st.markdown("#### 🕒 Jadwal Shift (System)")
    col_sched1, col_sched2 = st.columns(2)
    with col_sched1:
        default_sched_in = datetime.strptime("08:30", "%H:%M").time()
        sched_in = st.time_input("Mulai Shift (System)", value=default_sched_in, disabled=is_weekend)
    with col_sched2:
        default_sched_out = datetime.strptime("17:30", "%H:%M").time()
        sched_out = st.time_input("Pulang Shift (System)", value=default_sched_out, disabled=is_weekend)

    st.markdown("#### ⚡ Jadwal Lembur Aktual")
    col_ot1, col_ot2 = st.columns(2)
    with col_ot1:
        ot_in = st.time_input("Mulai Lembur", value=default_sched_out)
    with col_ot2:
        ot_out = st.time_input("Selesai Lembur", value=datetime.strptime("20:00", "%H:%M").time())

    if st.button("Hitung Durasi (SUBMIT)", type="primary"):
        # --- LOGIC PYTHON ---
        def combine_dt(t_obj):
            return datetime.combine(tgl_lembur, t_obj)

        dt_sched_in = combine_dt(sched_in)
        dt_sched_out = combine_dt(sched_out)
        dt_ot_in = combine_dt(ot_in)
        dt_ot_out = combine_dt(ot_out)

        if dt_sched_out <= dt_sched_in:
            dt_sched_out += timedelta(days=1)
        
        if dt_ot_out <= dt_ot_in:
            dt_ot_out += timedelta(days=1)

        dur_before = timedelta()
        dur_after = timedelta()
        break_before = timedelta()
        break_after = timedelta()
        case_name = "UNKNOWN"
        
        def format_td(td):
            total_sec = td.total_seconds()
            h = int(total_sec // 3600)
            m = int((total_sec % 3600) // 60)
            return f"{h} Jam {m} Menit"

        if is_weekend:
            case_name = "CASE 4: Lembur di Hari Libur / Weekend"
            diff_raw = dt_ot_out - dt_ot_in
            dur_after = diff_raw
        else:
            if dt_ot_in < dt_sched_out:
                case_name = f"CASE 1: Lembur Setelah Jam Kerja (Dimulai Sebelum {sched_out.strftime('%H:%M')})"
                if dt_ot_in < dt_sched_out:
                    dur_before = dt_sched_out - dt_ot_in
                if dt_ot_out > dt_sched_out:
                    dur_after = dt_ot_out - dt_sched_out
            elif dt_ot_in >= dt_sched_out:
                if ot_out < sched_in:
                    case_name = "CASE 3: Lembur Sebelum Jam Kerja (Overnight)"
                else:
                    case_name = f"CASE 2: Lembur Setelah Jam Kerja (Dimulai Setelah {sched_out.strftime('%H:%M')})"
                dur_after = dt_ot_out - dt_sched_out
                break_after = dt_ot_in - dt_sched_out

        total_duration = dur_before + dur_after - break_before - break_after
        
        if total_duration.total_seconds() < 0:
            total_duration = timedelta()

        st.markdown("---")
        st.subheader("📊 Hasil Perhitungan")
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            if not is_weekend:
                st.metric("Overtime Before Duration", format_td(dur_before))
                st.metric("Break Before Duration", format_td(break_before))
            else:
                st.info(f"Schedule In: **{ot_in.strftime('%H:%M')}** | Schedule Out: **{ot_out.strftime('%H:%M')}**")
            
        with col_res2:
            st.metric("Overtime After Duration", format_td(dur_after))
            if not is_weekend:
                st.metric("Break After Duration", format_td(break_after))
        
        st.markdown("---")
        st.success(f"**TOTAL LEMBUR: {format_td(total_duration)}**")
        st.caption(f"Kategori: {case_name}")

# --- FITUR: TOOLS PDF & FILE ---
def show_pdf_tools():
    st.title("🛠️ Tools PDF & File")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["📑 Merge PDF", "📝 Word to PDF"])

    # --- TAB 1: MERGE PDF ---
    with tab1:
        st.subheader("Gabungkan File PDF")
        uploaded_pdfs = st.file_uploader("Pilih beberapa file PDF", type="pdf", accept_multiple_files=True, key="merge_pdf_uploader")
        
        if uploaded_pdfs:
            if st.button("Gabungkan PDF", type="primary"):
                try:
                    writer = PdfWriter()
                    for pdf in uploaded_pdfs:
                        reader = PdfReader(pdf)
                        for page in reader.pages:
                            writer.add_page(page)
                    
                    buffer = io.BytesIO()
                    writer.write(buffer)
                    buffer.seek(0)
                    
                    st.success(f"Berhasil menggabungkan {len(uploaded_pdfs)} file PDF!")
                    st.download_button(
                        label="📥 Download Hasil Gabungan",
                        data=buffer,
                        file_name="merged_document.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Terjadi error saat menggabungkan: {e}")

    # --- TAB 2: WORD TO PDF (SMART LOGIC) ---
    with tab2:
        st.subheader("Convert Word ke PDF")
        st.info("Pilih file Word (.docx). Hasil akan dijadikan satu file ZIP.")
        
        uploaded_docxs = st.file_uploader("Pilih file Word (.docx)", type="docx", accept_multiple_files=True, key="word_to_pdf_uploader")
        
        if uploaded_docxs:
            if st.button("Convert Semua ke PDF", type="primary"):
                is_windows = platform.system() == "Windows"
                zip_buffer = io.BytesIO()
                
                # Progress Bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                error_found = False

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        for i, docx_file in enumerate(uploaded_docxs):
                            status_text.text(f"Memproses {i+1}/{len(uploaded_docxs)}: {docx_file.name}")
                            
                            base_name = os.path.splitext(docx_file.name)[0]
                            temp_docx_path = os.path.join(temp_dir, f"temp_{i}.docx")
                            temp_pdf_path = os.path.join(temp_dir, f"temp_{i}.pdf")
                            
                            # Simpan file upload ke temp
                            with open(temp_docx_path, "wb") as f:
                                f.write(docx_file.getbuffer())
                            
                            converted = False

                            # 1. COBA PAKAI MS WORD (WINDOWS ONLY)
                            if is_windows:
                                try:
                                    import pythoncom
                                    pythoncom.CoInitialize()
                                    from docx2pdf import convert
                                    convert(temp_docx_path, temp_pdf_path)
                                    pythoncom.CoUninitialize()
                                    converted = True
                                except Exception as e:
                                    st.warning(f"Gagal convert via MS Word ({docx_file.name}): {e}")
                            
                            # 2. COBA PAKAI LIBREOFFICE (LINUX/STREAMLIT CLOUD)
                            # LibreOffice command: soffice --headless --convert-to pdf
                            if not converted:
                                try:
                                    # Cek apakah soffice ada
                                    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', temp_docx_path, '--outdir', temp_dir], check=True, capture_output=True)
                                    # LibreOffice hasilnya kadang namanya beda, jadi cek file pdf yang baru dibuat
                                    # Di beberapa versi, output nama file mengikuti input
                                    if os.path.exists(temp_pdf_path):
                                        converted = True
                                    else:
                                        # Kadang libreoffice bikin file dengan nama asli
                                        possible_pdf = os.path.join(temp_dir, f"{base_name}.pdf")
                                        if os.path.exists(possible_pdf):
                                            os.rename(possible_pdf, temp_pdf_path)
                                            converted = True
                                except Exception as e:
                                    st.warning(f"Gagal convert via LibreOffice ({docx_file.name}). Pastikan sudah diinstal di server.")
                            
                            # Masukin ke ZIP kalo berhasil
                            if converted and os.path.exists(temp_pdf_path):
                                with open(temp_pdf_path, "rb") as f:
                                    pdf_data = f.read()
                                zf.writestr(f"{base_name}.pdf", pdf_data)
                            else:
                                error_found = True

                            progress_bar.progress((i + 1) / len(uploaded_docxs))

                status_text.text("Selesai!")
                zip_buffer.seek(0)

                if error_found:
                    st.warning("Beberapa file gagal dikonversi. Pastikan server mendukung konversi (MS Word di Windows atau LibreOffice di Linux).")
                
                st.success(f"Proses selesai!")
                st.download_button(
                    label="📥 Download Semua PDF (ZIP)",
                    data=zip_buffer,
                    file_name="converted_documents.zip",
                    mime="application/zip"
                )

# --- HALAMAN LOGIN ---
def show_login_page():
    st.title("🔒 Login Sistem Lembur")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Login Admin", use_container_width=True):
                if username in users_db and users_db[username] == password:
                    st.session_state.logged_in = True
                    st.session_state.role = "Admin"
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")
        
        with col_btn2:
            if st.button("Login as Guest", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.role = "Guest"
                st.session_state.username = "Guest"
                st.rerun()

# --- HALAMAN GUEST ---
def show_guest_view():
    st.title("👥 Rekap & Download Lembur")
    st.markdown("---")
    
    df = load_db()
    
    if df.empty:
        st.info("Belum ada data lembur yang tercatat.")
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
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
        st.metric(f"Total Jam Lembur", f"{total_jam} Jam")
        st.markdown("---")

        for i, row in df_show.iterrows():
            with st.container():
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.write(f"**{row['Nama']}** | {row['Periode_Lembur']}")
                    st.caption(f"Durasi: {row['Total_Jam']} Jam | Lokasi: {row['Lokasi']}")
                
                with col_btn:
                    file_path = row['FilePath']
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as fp:
                            st.download_button(
                                label="📥 Download",
                                data=fp,
                                file_name=os.path.basename(file_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_{i}"
                            )
                    else:
                        st.warning("File hilang")
                st.markdown("---")
    else:
        st.warning("Tidak ada data untuk filter ini.")

# --- HALAMAN ADMIN ---
def show_admin_view():
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role}")
        st.markdown("---")
        # Menu ditambah "Tools PDF" & "Kalkulator Lembur"
        menu = st.radio("Navigation", ["Create Surat", "Dashboard", "Data & Hapus", "Tools PDF", "Kalkulator Lembur"])
        st.markdown("---")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    if menu == "Create Surat":
        show_form_content()
    elif menu == "Dashboard":
        show_dashboard()
    elif menu == "Data & Hapus":
        show_data_management()
    elif menu == "Tools PDF":
        show_pdf_tools()
    elif menu == "Kalkulator Lembur":
        show_overtime_calculator()

# --- SUB-MENU ADMIN: FORM ---
def show_form_content():
    st.title("📄 Form Surat Tugas Lembur")
    st.markdown("**PT. Lintas Media Danawa**")
    st.markdown("---")

    st.subheader("Data Karyawan")
    pilih_nama = st.selectbox("Pilih Nama Karyawan", list(data_karyawan.keys()))
    nik_otomatis = data_karyawan[pilih_nama]
    st.text_input("NIK (Otomatis)", value=nik_otomatis, disabled=True)

    st.subheader("Data Atasan")
    pilih_atasan = st.selectbox("Pilih Atasan Penyetuju", list(data_atasan.keys()))
    nik_bos_otomatis = data_atasan[pilih_atasan]
    st.text_input("NIK Atasan (Otomatis)", value=nik_bos_otomatis, disabled=True)

    st.markdown("---")

    st.subheader("Detail Lembur")
    col1, col2 = st.columns(2)

    with col1:
        bagian = st.selectbox("Bagian/Divisi", ["IT Business Partner", "IT Infrastructure"])
        st.write("**Periode Lembur:**")
        tanggal_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.today(), datetime.today()))
        
    with col2:
        lokasi = st.selectbox("Lokasi Kerja", ["Remote (Work From Home)", "Arcadia", "TB. Simatupang"])
        jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
        jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("21:00", "%H:%M").time())

    uraian = st.text_area("Uraian Tugas / Pelaksanaan Lembur", height=100)

    st.markdown("---")
    if st.button("Generate & Save", type="primary"):
        try:
            if isinstance(tanggal_range, tuple) and len(tanggal_range) == 2:
                tgl_mulai = tanggal_range[0]
                tgl_selesai = tanggal_range[1]
            else:
                tgl_mulai = tanggal_range
                tgl_selesai = tanggal_range

            doc = DocxTemplate("template_surat.docx")
            
            tanggal_rapi = format_tanggal_range(tgl_mulai, tgl_selesai)
            durasi_text, durasi_jam = hitung_durasi(jam_mulai, jam_selesai)
            
            wib_timezone = timezone(timedelta(hours=7))
            tanggal_hari_ini = datetime.now(wib_timezone)
            tgl_acc_rapi = format_tanpa_hari(tanggal_hari_ini)
            
            uraian_bold = RichText(uraian, bold=True)
            
            context = {
                'nama': pilih_nama,
                'nik': nik_otomatis,
                'bagian': bagian,
                'lokasi': lokasi,
                'hari_tanggal': tanggal_rapi,
                'durasi': durasi_text,
                'pelaksanaan_lembur': uraian_bold,
                'namabos': pilih_atasan,
                'nikbos': nik_bos_otomatis,
                'tglacc': tgl_acc_rapi
            }
            
            doc.render(context)
            
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"SuratLembur_{pilih_nama.replace(' ', '_')}_{timestamp_str}.docx"
            file_path = os.path.join(DOCS_FOLDER, filename)
            
            doc.save(file_path)
            
            data_simpan = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Nama": pilih_nama,
                "NIK": nik_otomatis,
                "Bagian": bagian,
                "Lokasi": lokasi,
                "Periode_Lembur": tanggal_rapi,
                "Total_Jam": durasi_jam,
                "Uraian": uraian,
                "Atasan": pilih_atasan,
                "FilePath": file_path
            }
            save_to_db(data_simpan)
            
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            
            st.success("Data Tersimpan & Surat Berhasil Dibuat! 🎉")
            st.download_button(
                label="📥 Download Surat Lembur (.docx)",
                data=buffer,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

# --- SUB-MENU ADMIN: DASHBOARD ---
def show_dashboard():
    st.title("📊 Dashboard Rekap Lembur")
    
    df = load_db()
    
    if df.empty:
        st.warning("Data masih kosong.")
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    list_bulan = df['Bulan'].unique()
    pilih_bulan = st.selectbox("Pilih Bulan", list_bulan)

    df_filtered = df[df['Bulan'] == pilih_bulan]

    st.markdown("---")
    st.subheader("Rekap Per Karyawan")

    rekap = df_filtered.groupby('Nama')['Total_Jam'].sum().reset_index()

    for i, row in rekap.iterrows():
        col_nama, col_jam, col_aksi = st.columns([2, 1, 1])
        col_nama.write(f"**{row['Nama']}**")
        col_jam.metric("Jam", f"{row['Total_Jam']}")

        files_person = df_filtered[df_filtered['Nama'] == row['Nama']]
        
        with col_aksi:
            with st.expander("Detail"):
                if not files_person.empty:
                    for x, data_row in files_person.iterrows():
                        st.write(f"Tgl: {data_row['Periode_Lembur']} ({data_row['Total_Jam']} Jam)")
                        file_p = data_row['FilePath']
                        if os.path.exists(file_p):
                            with open(file_p, "rb") as fp:
                                st.download_button(
                                    label="Download Surat",
                                    data=fp,
                                    file_name=os.path.basename(file_p),
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dash_dl_{x}"
                                )
        
        st.markdown("---")

# --- SUB-MENU ADMIN: DATA & HAPUS ---
def show_data_management():
    st.title("⚙️ Manajemen Data Lembur")
    
    df = load_db()
    
    if df.empty:
        st.info("Tidak ada data.")
        return

    st.subheader("Data Lengkap")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("Hapus Data")
    
    list_timestamp = df['Timestamp'].tolist()
    selected_ts = st.selectbox("Pilih Data (Waktu)", list_timestamp)

    if st.button("Hapus Data Terpilih", type="secondary"):
        file_to_delete = df[df['Timestamp'] == selected_ts]['FilePath'].values[0]
        
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)
        
        df_baru = df[df['Timestamp'] != selected_ts]
        df_baru.to_csv(DB_FILE, index=False)
        
        st.success("Data & File berhasil dihapus!")
        st.rerun()

# --- MAIN LOGIC ---
def main():
    init_db()
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login_page()
    else:
        if st.session_state.role == "Admin":
            show_admin_view()
        elif st.session_state.role == "Guest":
            with st.sidebar:
                st.title("Menu Guest")
                guest_menu = st.radio("Navigation", ["Rekap Lembur", "Tools PDF", "Kalkulator Lembur"])
                st.markdown("---")
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.rerun()
            
            if guest_menu == "Rekap Lembur":
                show_guest_view()
            elif guest_menu == "Tools PDF":
                show_pdf_tools()
            elif guest_menu == "Kalkulator Lembur":
                show_overtime_calculator()

if __name__ == "__main__":
    main()
