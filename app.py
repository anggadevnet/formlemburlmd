import streamlit as st
from docxtpl import DocxTemplate, RichText
from datetime import datetime, timedelta, timezone
import io
import pandas as pd
from io import StringIO
from github import Github

# --- KONFIGURASI HARD CODED (UNTUK TEST) ---
GITHUB_TOKEN = "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"
REPO_NAME = "anggadevnet/formlemburlmd"

# --- DATABASE KARYAWAN & ATASAN ---
data_karyawan = {
    "ANGGA SEPTIAN CAHYA": "09244925",
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
    "admin": "admin123"
}

# --- GITHUB HELPER FUNCTIONS ---
def get_github_repo():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        return repo
    except Exception as e:
        st.error(f"Gagal koneksi GitHub: {e}")
        return None

def get_csv_data():
    repo = get_github_repo()
    if not repo: return pd.DataFrame()
    
    try:
        contents = repo.get_contents("database.csv")
        data = contents.decoded_content.decode("utf-8")
        df = pd.read_csv(StringIO(data))
        return df
    except:
        # Kalau file belum ada, bikin dataframe kosong
        return pd.DataFrame(columns=[
            "Timestamp", "Nama", "NIK", "Bagian", "Lokasi", 
            "Periode_Lembur", "Total_Jam", "Uraian", "Atasan", "Tanggal_ACC", "Durasi_Text"
        ])

def save_csv_data(df):
    repo = get_github_repo()
    if not repo: return False
    
    try:
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        new_content = csv_buffer.getvalue()
        
        # Cek apakah file sudah ada
        try:
            contents = repo.get_contents("database.csv")
            # Kalau ada, Update
            repo.update_file(contents.path, "Update database lembur", new_content, contents.sha)
        except:
            # Kalau belum ada, Create baru
            repo.create_file("database.csv", "Create database lembur", new_content)
            
        return True
    except Exception as e:
        st.error(f"Gagal save ke GitHub: {e}")
        return False

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
    from datetime import datetime, timedelta
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

def generate_word_file(data_row):
    doc = DocxTemplate("template_surat.docx")
    uraian_bold = RichText(data_row['Uraian'], bold=True)
    
    context = {
        'nama': data_row['Nama'],
        'nik': data_row['NIK'],
        'bagian': data_row['Bagian'],
        'lokasi': data_row['Lokasi'],
        'hari_tanggal': data_row['Periode_Lembur'],
        'durasi': data_row['Durasi_Text'], 
        'pelaksanaan_lembur': uraian_bold,
        'namabos': data_row['Atasan'],
        'nikbos': data_atasan.get(data_row['Atasan'], ''),
        'tglacc': data_row['Tanggal_ACC']
    }
    
    doc.render(context)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

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
    st.title("👥 Rekap Lembur")
    st.markdown("---")
    
    df = get_csv_data()
    
    if df.empty:
        st.info("Belum ada data.")
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp'])
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
        total_jam = df_show['Total_Jam'].astype(int).sum()
        st.metric("Total Jam Lembur", f"{total_jam} Jam")
        st.markdown("---")

        for i, row in df_show.iterrows():
            with st.container():
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.write(f"**{row['Nama']}** | {row['Periode_Lembur']}")
                    st.caption(f"Durasi: {row['Total_Jam']} Jam")
                
                with col_btn:
                    buffer = generate_word_file(row)
                    st.download_button(
                        label="📥 Download",
                        data=buffer,
                        file_name=f"Surat_Lembur_{row['Nama']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"guest_dl_{i}"
                    )
                st.markdown("---")

# --- HALAMAN ADMIN ---
def show_admin_view():
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username}")
        st.markdown("---")
        menu = st.radio("Navigation", ["Create Surat", "Dashboard", "Data & Hapus"])
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

# --- FORM CONTENT ---
def show_form_content():
    st.title("📄 Form Surat Tugas Lembur")
    st.markdown("---")

    st.subheader("Data Karyawan")
    pilih_nama = st.selectbox("Pilih Nama Karyawan", list(data_karyawan.keys()))
    nik_otomatis = data_karyawan[pilih_nama]
    st.text_input("NIK (Otomatis)", value=nik_otomatis, disabled=True)

    st.subheader("Data Atasan")
    pilih_atasan = st.selectbox("Pilih Atasan Penyetuju", list(data_atasan.keys()))
    
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

    uraian = st.text_area("Uraian Tugas", height=100)

    st.markdown("---")
    if st.button("Simpan & Generate", type="primary"):
        try:
            if isinstance(tanggal_range, tuple):
                tgl_mulai, tgl_selesai = tanggal_range[0], tanggal_range[1]
            else:
                tgl_mulai, tgl_selesai = tanggal_range, tanggal_range

            tanggal_rapi = format_tanggal_range(tgl_mulai, tgl_selesai)
            durasi_text, durasi_jam = hitung_durasi(jam_mulai, jam_selesai)
            
            wib_timezone = timezone(timedelta(hours=7))
            tanggal_hari_ini = datetime.now(wib_timezone)
            tgl_acc_rapi = format_tanpa_hari(tanggal_hari_ini)
            
            data_simpan = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Nama": pilih_nama,
                "NIK": nik_otomatis,
                "Bagian": bagian,
                "Lokasi": lokasi,
                "Periode_Lembur": tanggal_rapi,
                "Total_Jam": str(durasi_jam),
                "Uraian": uraian,
                "Atasan": pilih_atasan,
                "Tanggal_ACC": tgl_acc_rapi,
                "Durasi_Text": durasi_text
            }

            df_old = get_csv_data()
            df_new = pd.concat([df_old, pd.DataFrame([data_simpan])], ignore_index=True)
            
            if save_csv_data(df_new):
                st.success("Data Tersimpan ke GitHub! 🎉")
                buffer = generate_word_file(data_simpan)
                st.download_button(
                    label="📥 Download Surat Lembur (.docx)",
                    data=buffer,
                    file_name=f"Surat_Lembur_{pilih_nama}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.error("Gagal menyimpan data.")
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

# --- DASHBOARD ---
def show_dashboard():
    st.title("📊 Dashboard")
    df = get_csv_data()
    if df.empty: return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    list_bulan = df['Bulan'].unique()
    pilih_bulan = st.selectbox("Pilih Bulan", list_bulan)

    df_filtered = df[df['Bulan'] == pilih_bulan]
    st.metric("Total Jam Bulan Ini", f"{df_filtered['Total_Jam'].astype(int).sum()} Jam")
    
    rekap = df_filtered.groupby('Nama')['Total_Jam'].sum().reset_index()
    st.dataframe(rekap)

# --- DATA MANAGEMENT ---
def show_data_management():
    st.title("⚙️ Manajemen Data")
    df = get_csv_data()
    st.dataframe(df)
    
    if not df.empty:
        st.subheader("Hapus Data")
        list_timestamp = df['Timestamp'].tolist()
        selected_ts = st.selectbox("Pilih Data", list_timestamp)
        
        if st.button("Hapus Data Terpilih"):
            df_new = df[df['Timestamp'] != selected_ts]
            if save_csv_data(df_new):
                st.success("Data berhasil dihapus!")
                st.rerun()

# --- MAIN ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login_page()
    else:
        if st.session_state.role == "Admin":
            show_admin_view()
        else:
            with st.sidebar:
                st.title("Menu Guest")
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.rerun()
            show_guest_view()

if __name__ == "__main__":
    main()
