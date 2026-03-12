import streamlit as st
from docxtpl import DocxTemplate
from datetime import datetime, timedelta
import io

# --- DATABASE KARYAWAN & ATASAN ---
# Format: "Nama" : "NIK"
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

# --- SETTING HALAMAN ---
st.set_page_config(page_title="Form Lembur LMD", page_icon="📄")

# --- FUNGSI BANTUAN ---
def format_tanggal_indonesia(tanggal_obj):
    hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    
    hari = hari_list[tanggal_obj.weekday()]
    tanggal = tanggal_obj.day
    bulan = bulan_list[tanggal_obj.month - 1]
    tahun = tanggal_obj.year
    
    return f"{hari}, {tanggal} {bulan} {tahun}"

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
    
    return f"{mulai_str} - {selesai_str} , {teks_jam}"

# --- TAMPILAN WEB ---
st.title("📄 Form Surat Tugas Lembur")
st.markdown("**PT. Lintas Media Danawa**")
st.markdown("---")

# Bagian Pilih Karyawan
st.subheader("Data Karyawan")
pilih_nama = st.selectbox("Pilih Nama Karyawan", list(data_karyawan.keys()))
nik_otomatis = data_karyawan[pilih_nama]

# Tampilkan NIK secara otomatis (Read Only)
st.text_input("NIK (Otomatis)", value=nik_otomatis, disabled=True)

# Bagian Pilih Atasan
st.subheader("Data Atasan")
pilih_atasan = st.selectbox("Pilih Atasan Penyetuju", list(data_atasan.keys()))
nik_bos_otomatis = data_atasan[pilih_atasan]
st.text_input("NIK Atasan (Otomatis)", value=nik_bos_otomatis, disabled=True)

st.markdown("---")

# Bagian Detail Lembur
st.subheader("Detail Lembur")
col1, col2 = st.columns(2)

with col1:
    bagian = st.text_input("Bagian/Divisi")
    tanggal = st.date_input("Tanggal Lembur", datetime.today())

with col2:
    lokasi = st.text_input("Lokasi Kerja")
    jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
    jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("21:00", "%H:%M").time())

uraian = st.text_area("Uraian Tugas / Pelaksanaan Lembur", height=100)

# Tombol Proses
st.markdown("---")
if st.button("Generate Surat Word", type="primary"):
    try:
        # Load Template
        doc = DocxTemplate("template_surat.docx")
        
        # Proses Data
        tanggal_rapi = format_tanggal_indonesia(tanggal)
        durasi_rapi = hitung_durasi(jam_mulai, jam_selesai)
        
        # Siapkan Context (Variabel untuk Word)
        context = {
            'nama': pilih_nama,
            'nik': nik_otomatis,
            'bagian': bagian,
            'lokasi': lokasi,
            'hari_tanggal': tanggal_rapi,
            'durasi': durasi_rapi,
            'pelaksanaan_lembur': uraian,
            'namabos': pilih_atasan,    # Tambahan baru
            'nikbos': nik_bos_otomatis  # Tambahan baru
        }
        
        # Render ke Word
        doc.render(context)
        
        # Simpan ke memory
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        # Tombol Download
        st.success("Surat Berhasil Dibuat! 🎉")
        st.download_button(
            label="📥 Download Surat Lembur (.docx)",
            data=buffer,
            file_name=f"Surat_Lembur_{pilih_nama}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

st.caption("Developed by Admin - Powered by Streamlit")
