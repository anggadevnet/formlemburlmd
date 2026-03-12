import streamlit as st
from docxtpl import DocxTemplate
from datetime import datetime, timedelta
import io

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
    # Hitung selisih detik
    delta = datetime.combine(datetime.min, selesai_obj) - datetime.combine(datetime.min, mulai_obj)
    
    # Kalau minus (balik tengah malam), tambah 24 jam
    if delta.total_seconds() < 0:
        delta = delta + timedelta(days=1)
        
    total_jam = int(delta.total_seconds() // 3600)
    total_menit = int((delta.total_seconds() % 3600) // 60)
    
    teks_jam = f"{total_jam} jam"
    if total_menit > 0:
        teks_jam += f" {total_menit} menit"
        
    # Format string
    mulai_str = mulai_obj.strftime("%H:%M")
    selesai_str = selesai_obj.strftime("%H:%M")
    
    return f"{mulai_str} - {selesai_str} , {teks_jam}"

# --- TAMPILAN WEB ---
st.title("📄 Form Surat Tugas Lembur")
st.markdown("**PT. Lintas Media Danawa**")
st.markdown("---")

# Kolom Input
col1, col2 = st.columns(2)

with col1:
    nama = st.text_input("Nama Lengkap")
    nik = st.text_input("NIK")
    bagian = st.text_input("Bagian/Divisi")
    lokasi = st.text_input("Lokasi Kerja")

with col2:
    tanggal = st.date_input("Tanggal Lembur", datetime.today())
    jam_mulai = st.time_input("Jam Mulai", value=datetime.strptime("17:00", "%H:%M").time())
    jam_selesai = st.time_input("Jam Selesai", value=datetime.strptime("21:00", "%H:%M").time())

uraian = st.text_area("Uraian Tugas / Pelaksanaan Lembur", height=100)

# Tombol Proses
if st.button("Generate Surat Word", type="primary"):
    if not nama or not nik:
        st.error("Nama dan NIK wajib diisi!")
    else:
        try:
            # Load Template
            doc = DocxTemplate("template_surat.docx")
            
            # Proses Data
            tanggal_rapi = format_tanggal_indonesia(tanggal)
            durasi_rapi = hitung_durasi(jam_mulai, jam_selesai)
            
            context = {
                'nama': nama,
                'nik': nik,
                'bagian': bagian,
                'lokasi': lokasi,
                'hari_tanggal': tanggal_rapi,
                'durasi': durasi_rapi,
                'pelaksanaan_lembur': uraian
            }
            
            # Render ke Word
            doc.render(context)
            
            # Simpan ke memory (biar bisa download)
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            
            # Tombol Download
            st.success("Surat Berhasil Dibuat! 🎉")
            st.download_button(
                label="📥 Download Surat Lembur (.docx)",
                data=buffer,
                file_name=f"Surat_Lembur_{nama}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

st.markdown("---")
st.caption("Developed by Admin - Powered by Streamlit")