import streamlit as st
from docxtpl import DocxTemplate
from datetime import datetime, timedelta
import io

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

# --- SETTING HALAMAN ---
st.set_page_config(page_title="Form Lembur LMD", page_icon="📄")

# --- FUNGSI BANTUAN ---
def format_tanggal_satu(tanggal_obj):
    hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    bulan_list = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    hari = hari_list[tanggal_obj.weekday()]
    bulan = bulan_list[tanggal_obj.month - 1]
    return f"{hari}, {tanggal_obj.day} {bulan} {tanggal_obj.year}"

# Fungsi format tanpa hari (Untuk Tgl ACC)
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
    return f"{mulai_str} - {selesai_str} , {teks_jam}"

# --- TAMPILAN WEB ---
st.title("📄 Form Surat Tugas Lembur")
st.markdown("**PT. Lintas Media Danawa**")
st.markdown("---")

# Bagian Pilih Karyawan
st.subheader("Data Karyawan")
pilih_nama = st.selectbox("Pilih Nama Karyawan", list(data_karyawan.keys()))
nik_otomatis = data_karyawan[pilih_nama]
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
    bagian = st.selectbox("Bagian/Divisi", ["IT Business Partner", "IT Infrastructure"])
    st.write("**Periode Lembur:**")
    tanggal_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.today(), datetime.today()))
    
with col2:
    lokasi = st.selectbox("Lokasi Kerja", ["Remote (Work From Home)", "Arcadia", "TB. Simatupang"])
    jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
    jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("21:00", "%H:%M").time())

uraian = st.text_area("Uraian Tugas / Pelaksanaan Lembur", height=100)

# Tombol Proses
st.markdown("---")
if st.button("Generate Surat Word", type="primary"):
    try:
        # Validasi Tanggal Range
        if isinstance(tanggal_range, tuple) and len(tanggal_range) == 2:
            tgl_mulai = tanggal_range[0]
            tgl_selesai = tanggal_range[1]
        else:
            tgl_mulai = tanggal_range
            tgl_selesai = tanggal_range

        # Load Template
        doc = DocxTemplate("template_surat.docx")
        
        # Proses Data
        tanggal_rapi = format_tanggal_range(tgl_mulai, tgl_selesai)
        durasi_rapi = hitung_durasi(jam_mulai, jam_selesai)
        
        # PROSES TGL ACC = TANGGAL HARI INI
        tanggal_hari_ini = datetime.today()
        tgl_acc_rapi = format_tanpa_hari(tanggal_hari_ini)
        
        # Context
        context = {
            'nama': pilih_nama,
            'nik': nik_otomatis,
            'bagian': bagian,
            'lokasi': lokasi,
            'hari_tanggal': tanggal_rapi,
            'durasi': durasi_rapi,
            'pelaksanaan_lembur': uraian,
            'namabos': pilih_atasan,
            'nikbos': nik_bos_otomatis,
            'tglacc': tgl_acc_rapi  # Ini tanggal download
        }
        
        # Render
        doc.render(context)
        
        # Simpan ke memory
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        # Download
        st.success("Surat Berhasil Dibuat! 🎉")
        st.download_button(
            label="📥 Download Surat Lembur (.docx)",
            data=buffer,
            file_name=f"Surat_Lembur_{pilih_nama}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

st.caption("Developed by Acg - Powered by Streamlit")
