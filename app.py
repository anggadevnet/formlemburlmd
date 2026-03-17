import streamlit as st
from docxtpl import DocxTemplate, RichText
from datetime import datetime, timedelta, timezone
import io
import pandas as pd
import os

# --- CONFIG & DATABASE FILE ---
DB_FILE = 'database_lembur.csv'
DOCS_FOLDER = 'generated_docs'

# --- SETUP FOLDER ---
# Buat folder untuk nyimpen file hasil generate kalo belum ada
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

# --- HALAMAN GUEST (UPDATED) ---
def show_guest_view():
    st.title("👥 Rekap & Download Lembur")
    st.markdown("---")
    
    df = load_db()
    
    if df.empty:
        st.info("Belum ada data lembur yang tercatat.")
        return

    # Filter Data
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    # Filter Bulan
    list_bulan = df['Bulan'].unique()
    pilih_bulan = st.selectbox("Pilih Bulan", list_bulan)
    
    # Filter Nama
    df_filtered_month = df[df['Bulan'] == pilih_bulan]
    list_nama = df_filtered_month['Nama'].unique()
    pilih_nama = st.selectbox("Pilih Karyawan", ["Semua"] + list(list_nama))

    # Apply Filter
    if pilih_nama == "Semua":
        df_show = df_filtered_month
    else:
        df_show = df_filtered_month[df_filtered_month['Nama'] == pilih_nama]

    st.markdown("---")
    
    # Tampilkan Data & Tombol Download
    if df_show.empty:
        st.warning("Tidak ada data untuk filter ini.")
    else:
        # Summary
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
                    # Tombol Download File
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

# --- HALAMAN ADMIN ---
def show_admin_view():
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role}")
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

# --- SUB-MENU ADMIN: FORM (UPDATED TO SAVE FILE) ---
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
            
            # --- SAVE TO FILE & DATABASE ---
            # 1. Buat nama file unik
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"SuratLembur_{pilih_nama.replace(' ', '_')}_{timestamp_str}.docx"
            file_path = os.path.join(DOCS_FOLDER, filename)
            
            # 2. Simpan file fisik ke folder generated_docs
            doc.save(file_path)
            
            # 3. Simpan info ke CSV
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
            
            # 4. Siapkan buffer untuk download langsung
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

# --- SUB-MENU ADMIN: DASHBOARD (UPDATED) ---
def show_dashboard():
    st.title("📊 Dashboard Rekap Lembur")
    
    df = load_db()
    
    if df.empty:
        st.warning("Data masih kosong.")
        return

    # Filter Bulan
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Bulan'] = df['Timestamp'].dt.to_period('M').astype(str)
    
    list_bulan = df['Bulan'].unique()
    pilih_bulan = st.selectbox("Pilih Bulan", list_bulan)

    df_filtered = df[df['Bulan'] == pilih_bulan]

    st.markdown("---")
    st.subheader("Rekap Per Karyawan")

    # Group by Nama
    rekap = df_filtered.groupby('Nama')['Total_Jam'].sum().reset_index()

    # Tampilkan per nama
    for i, row in rekap.iterrows():
        col_nama, col_jam, col_aksi = st.columns([2, 1, 1])
        col_nama.write(f"**{row['Nama']}**")
        col_jam.metric("Jam", f"{row['Total_Jam']}")

        # Tombol untuk lihat detail / download per orang
        files_person = df_filtered[df_filtered['Nama'] == row['Nama']]
        
        with col_aksi:
            # Buat tombol expand detail
            with st.expander("Detail"):
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
        # Ambil path file buat dihapus juga
        file_to_delete = df[df['Timestamp'] == selected_ts]['FilePath'].values[0]
        
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete) # Hapus file fisik
        
        # Hapus dari CSV
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
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.rerun()
            show_guest_view()

if __name__ == "__main__":
    main()
