import streamlit as st
from docxtpl import DocxTemplate, RichText
from datetime import datetime, timedelta, timezone, time, date
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
    "ANGGA SEPTIAN CAHYA": {"nik": "09244925", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner"},
    "NADINE PUSPITA SARI": {"nik": "09244924", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner"},
    "MOHAMMAD SYAIFUL ICHSAN": {"nik": "09244931", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner"},
    "NAFIRA NURZAHRA": {"nik": "09244914", "atasan": "ERWIN SETIAWAN", "bagian": "IT Business Partner"},
    "MOCH DIKI RAMDANI": {"nik": "09244923", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure"},
    "MUKHLIS": {"nik": "09244929", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure"},
    "AZIS SAEFUDIN": {"nik": "09244926", "atasan": "ARIS KURNIAWAN NOOR", "bagian": "IT Infrastructure"}
}
data_atasan = {
    "ERWIN SETIAWAN": "82233018",
    "ARIS KURNIAWAN NOOR": "89111077"
}
users_db = {"admin": "admin123", "hrd": "hrd123"}

# --- FUNGSI GITHUB HELPER (UNTUK PERSISTENCE) ---
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
        st.error(f"Error Sync: {e}")
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
    
    # Auto Sync ke GitHub
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
    return f"{mulai_obj.strftime('%H:%M')} - {selesai_obj.strftime('%H:%M')} , {teks_jam}", total_jam

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
                        st.download_button("📥 Download", data=buffer, file_name="merged_document.pdf", mime="application/pdf")
                    except Exception as e: st.error(f"Error: {e}")

    with tab2:
        st.subheader("Convert Word ke PDF")
        libreoffice_exists = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice_exists: st.error("❌ LibreOffice tidak ditemukan.")
        uploaded_docxs = st.file_uploader("Pilih file Word (.docx)", type="docx", accept_multiple_files=True, key="word_to_pdf_uploader")
        if uploaded_docxs and st.button("Convert Semua ke PDF", type="primary"):
            if not libreoffice_exists: st.error("Gagal.")
            else:
                try:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        with tempfile.TemporaryDirectory() as temp_dir:
                            for i, docx_file in enumerate(uploaded_docxs):
                                input_path = os.path.join(temp_dir, f"temp_{i}.docx")
                                with open(input_path, "wb") as f: f.write(docx_file.getbuffer())
                                subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp_dir, input_path], capture_output=True)
                                output_pdf = os.path.join(temp_dir, f"temp_{i}.pdf")
                                if os.path.exists(output_pdf):
                                    with open(output_pdf, "rb") as pdf_file: zf.writestr(f"{os.path.splitext(docx_file.name)[0]}.pdf", pdf_file.read())
                    zip_buffer.seek(0)
                    st.success("Berhasil convert!")
                    st.download_button("📥 Download ZIP", data=zip_buffer, file_name="converted_docs.zip", mime="application/zip")
                except Exception as e: st.error(f"Error: {e}")

# --- FITUR KALKULATOR LEMBUR (LENGKAP) ---
def show_overtime_calculator():
    st.title("⏱️ Kalkulator Durasi Lembur")
    st.markdown("---")
    st.markdown("Isi data dibawah ini untuk menghitung durasi lembur otomatis.")
    
    col_date, col_weekend = st.columns([2, 1])
    with col_date: tgl_lembur = st.date_input("Tanggal Lembur", value=date.today())
    with col_weekend: is_weekend = st.checkbox("Weekend / Holiday (CASE 4)", value=False)

    st.markdown("#### 🕒 Jadwal Shift (System)")
    col_sched1, col_sched2 = st.columns(2)
    with col_sched1: sched_in = st.time_input("Mulai Shift (System)", value=datetime.strptime("08:30", "%H:%M").time(), disabled=is_weekend)
    with col_sched2: sched_out = st.time_input("Pulang Shift (System)", value=datetime.strptime("17:30", "%H:%M").time(), disabled=is_weekend)

    st.markdown("#### ⚡ Jadwal Lembur Aktual")
    col_ot1, col_ot2 = st.columns(2)
    with col_ot1: ot_in = st.time_input("Mulai Lembur", value=sched_out)
    with col_ot2: ot_out = st.time_input("Selesai Lembur", value=datetime.strptime("20:00", "%H:%M").time())

    if st.button("Hitung Durasi (SUBMIT)", type="primary"):
        def combine_dt(t_obj): return datetime.combine(tgl_lembur, t_obj)
        dt_sched_in = combine_dt(sched_in); dt_sched_out = combine_dt(sched_out)
        dt_ot_in = combine_dt(ot_in); dt_ot_out = combine_dt(ot_out)
        if dt_sched_out <= dt_sched_in: dt_sched_out += timedelta(days=1)
        if dt_ot_out <= dt_ot_in: dt_ot_out += timedelta(days=1)

        dur_before = timedelta(); dur_after = timedelta()
        break_before = timedelta(); break_after = timedelta()
        case_name = "UNKNOWN"
        
        def format_td(td):
            total_sec = td.total_seconds(); h = int(total_sec // 3600); m = int((total_sec % 3600) // 60)
            return f"{h} Jam {m} Menit"

        if is_weekend:
            case_name = "CASE 4: Lembur di Hari Libur / Weekend"
            diff_raw = dt_ot_out - dt_ot_in; dur_after = diff_raw 
        else:
            if dt_ot_in < dt_sched_out:
                case_name = f"CASE 1: Lembur Setelah Jam Kerja (Dimulai Sebelum {sched_out.strftime('%H:%M')})"
                if dt_ot_in < dt_sched_out: dur_before = dt_sched_out - dt_ot_in
                if dt_ot_out > dt_sched_out: dur_after = dt_ot_out - dt_sched_out
            elif dt_ot_in >= dt_sched_out:
                if ot_out < sched_in: case_name = "CASE 3: Lembur Sebelum Jam Kerja (Overnight)"
                else: case_name = f"CASE 2: Lembur Setelah Jam Kerja (Dimulai Setelah {sched_out.strftime('%H:%M')})"
                dur_after = dt_ot_out - dt_sched_out
                break_after = dt_ot_in - dt_sched_out

        total_duration = dur_before + dur_after - break_before - break_after
        if total_duration.total_seconds() < 0: total_duration = timedelta()

        st.markdown("---"); st.subheader("📊 Hasil Perhitungan")
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            if not is_weekend:
                st.metric("Overtime Before Duration", format_td(dur_before))
                st.metric("Break Before Duration", format_td(break_before))
            else: st.info(f"Schedule In: **{ot_in.strftime('%H:%M')}** | Schedule Out: **{ot_out.strftime('%H:%M')}**")
        with col_res2:
            st.metric("Overtime After Duration", format_td(dur_after))
            if not is_weekend: st.metric("Break After Duration", format_td(break_after))
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
    df = load_db()
    if df.empty: st.info("Belum ada data."); return
    df['Timestamp'] = pd.to_datetime(df['Timestamp']); df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    pilih_bulan = st.selectbox("Pilih Bulan", df['Bulan'].unique())
    df_show = df[df['Bulan'] == pilih_bulan]
    st.metric("Total Jam", f"{df_show['Total_Jam'].sum()} Jam")
    for i, row in df_show.iterrows():
        with st.container():
            st.write(f"**{row['Nama']}** | {row['Periode_Lembur']}")
            if os.path.exists(row['FilePath']):
                with open(row['FilePath'], "rb") as fp:
                    st.download_button("Download", data=fp, file_name=os.path.basename(row['FilePath']), key=f"dl_{i}")

# --- HALAMAN ADMIN ---
def show_admin_view():
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username}")
        menu = st.radio("Navigation", ["Create Surat", "Dashboard", "Data & Hapus", "Tools PDF", "Kalkulator Lembur"])
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    if menu == "Create Surat": show_form_content()
    elif menu == "Dashboard": show_dashboard()
    elif menu == "Data & Hapus": show_data_management()
    elif menu == "Tools PDF": show_pdf_tools()
    elif menu == "Kalkulator Lembur": show_overtime_calculator()

# --- SUB-MENU ADMIN: FORM (OTOMATIS) ---
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
            
            # Push File ke GitHub
            if push_to_github(file_path, f"{DOCS_FOLDER}/{filename}", f"Add Surat: {pilih_nama}"):
                st.toast("☁️ File synced to GitHub!", icon="✅")
            
            save_to_db({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Nama": pilih_nama, "NIK": detail['nik'],
                "Bagian": detail['bagian'], "Lokasi": lokasi, "Periode_Lembur": tanggal_rapi, "Total_Jam": durasi_jam,
                "Uraian": uraian, "Atasan": detail['atasan'], "FilePath": file_path
            })
            
            buffer = io.BytesIO(); doc.save(buffer); buffer.seek(0)
            st.success("Data Tersimpan! 🎉")
            st.download_button("📥 Download", data=buffer, file_name=filename)
        except Exception as e: st.error(f"Error: {e}")

# --- SUB-MENU ADMIN: DASHBOARD (PER ORANG) ---
def show_dashboard():
    st.title("📊 Dashboard Rekap Lembur")
    df = load_db()
    if df.empty: st.warning("Data masih kosong."); return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    pilih_bulan = st.selectbox("Pilih Bulan", df['Bulan'].unique())
    df_filtered = df[df['Bulan'] == pilih_bulan]
    
    st.markdown("---")
    st.subheader("Rekap Per Karyawan")
    
    # Group by Nama
    rekap = df_filtered.groupby('Nama')['Total_Jam'].sum().reset_index()

    for i, row in rekap.iterrows():
        with st.container():
            col_nama, col_jam, col_aksi = st.columns([2, 1, 1])
            col_nama.write(f"**{row['Nama']}**")
            col_jam.metric("Jam", f"{row['Total_Jam']}")
            
            # Ambil detail file orang ini
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
                            else:
                                st.caption("File hilang")
        st.markdown("---")

# --- SUB-MENU ADMIN: DATA & HAPUS (FIXED) ---
def show_data_management():
    st.title("⚙️ Manajemen Data Lembur")
    df = load_db()
    if df.empty: st.info("Tidak ada data."); return
    
    st.subheader("Data Lengkap")
    st.dataframe(df, use_container_width=True)
    st.markdown("---")
    
    # --- Fitur Hapus ---
    st.subheader("Hapus Data")
    list_timestamp = df['Timestamp'].tolist()
    selected_ts = st.selectbox("Pilih Data (Waktu)", list_timestamp)
    
    if st.button("Hapus Data Terpilih", type="secondary"):
        # Ambil file path
        row_to_delete = df[df['Timestamp'] == selected_ts]
        if not row_to_delete.empty:
            file_to_delete = row_to_delete['FilePath'].values[0]
            
            # Hapus File Fisik
            if os.path.exists(file_to_delete):
                try:
                    os.remove(file_to_delete)
                except Exception as e:
                    st.warning(f"Gagal hapus file fisik: {e}")
            
            # Update DataFrame
            df_baru = df[df['Timestamp'] != selected_ts]
            df_baru.to_csv(DB_FILE, index=False)
            
            # Sync Perubahan ke GitHub
            push_to_github(DB_FILE, DB_FILE, f"Delete data: {selected_ts}")
            
            st.success("Data & File berhasil dihapus!")
            st.rerun()
    
    st.markdown("---")
    
    # --- Fitur Sync Manual ---
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
        st.error("❌ Secrets belum disetting.")

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
                guest_menu = st.radio("Navigation", ["Rekap Lembur", "Tools PDF", "Kalkulator Lembur"])
                if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
            
            if guest_menu == "Rekap Lembur": show_guest_view()
            elif guest_menu == "Tools PDF": show_pdf_tools()
            elif guest_menu == "Kalkulator Lembur": show_overtime_calculator()

if __name__ == "__main__":
    main()
