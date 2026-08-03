import io
import re
import sqlite3
import urllib.parse
import cv2
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Kütüphane Yönetimi", page_icon="📚", layout="centered")

# --- ÖZEL TEMA (CSS) ---
st.markdown("""
    <style>
    .stApp { background-color: #F5F2EB; color: #1A1A1A; }
    h1, h2, h3, h4, h5, h6, label, p, span { color: #2C3022 !important; font-family: 'Segoe UI', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { background-color: #4A5335 !important; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #F5F2EB !important; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #353B26 !important; color: #FFFFFF !important; border-radius: 6px; }
    .stButton>button, .stDownloadButton>button { background-color: #4A5335 !important; color: #F5F2EB !important; border-radius: 8px !important; border: none !important; font-weight: 600 !important; }
    .stButton>button:hover, .stDownloadButton>button:hover { background-color: #353B26 !important; color: #FFFFFF !important; }
    input, select, textarea, div[data-baseweb="select"] { background-color: #FFFFFF !important; color: #1A1A1A !important; border-radius: 6px !important; }
    div[data-testid="stExpander"] { background-color: #EAE5D9; border: 1px solid #D6CEBE; border-radius: 8px; margin-bottom: 8px; }
    [data-testid="stMetricValue"] { color: #4A5335 !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- VERİTABANI BAĞLANTISI ---
def get_db_connection():
    conn = sqlite3.connect("kutuphane.db", timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass
    return conn

conn = get_db_connection()
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS kitaplar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    yazar TEXT NOT NULL,
    kategori TEXT DEFAULT 'Genel',
    durum TEXT DEFAULT 'Kütüphanede',
    emanet_alan TEXT DEFAULT '',
    okundu_durum TEXT DEFAULT 'Okunmadı'
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS kategoriler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT UNIQUE NOT NULL
)
""")

c.execute("PRAGMA table_info(kitaplar)")
mevcut_sutunlar = [col[1] for col in c.fetchall()]

if "kategori" not in mevcut_sutunlar: c.execute("ALTER TABLE kitaplar ADD COLUMN kategori TEXT DEFAULT 'Genel'")
if "durum" not in mevcut_sutunlar: c.execute("ALTER TABLE kitaplar ADD COLUMN durum TEXT DEFAULT 'Kütüphanede'")
if "emanet_alan" not in mevcut_sutunlar: c.execute("ALTER TABLE kitaplar ADD COLUMN emanet_alan TEXT DEFAULT ''")
if "okundu_durum" not in mevcut_sutunlar: c.execute("ALTER TABLE kitaplar ADD COLUMN okundu_durum TEXT DEFAULT 'Okunmadı'")

conn.commit()

# --- BAŞLIK VE ÖZETLER ---
st.title("📚 Kütüphane Yönetim Sistemi")

c.execute("SELECT COUNT(*) FROM kitaplar")
toplam_kitap = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM kitaplar WHERE durum = 'Emanette'")
emanette_kitap = c.fetchone()[0]

m_col1, m_col2 = st.columns(2)
m_col1.metric(label="📖 Toplam Kitap Sayısı", value=toplam_kitap)
m_col2.metric(label="🔴 Emanetteki Kitap Sayısı", value=emanette_kitap)

st.divider()

# --- SESSION STATE TANIMLARI ---
if "form_key" not in st.session_state: st.session_state["form_key"] = 0
if "emanet_key" not in st.session_state: st.session_state["emanet_key"] = 0
if "kamera_acik" not in st.session_state: st.session_state["kamera_acik"] = False
if "scanned_id" not in st.session_state: st.session_state["scanned_id"] = None
if "camera_key" not in st.session_state: st.session_state["camera_key"] = 0

def emanet_sifirla():
    st.session_state["kamera_acik"] = False
    st.session_state["scanned_id"] = None
    st.session_state["emanet_key"] += 1
    st.session_state["camera_key"] += 1

tab_ekle, tab_liste, tab_emanet = st.tabs(["➕ Yeni Kitap Ekle", "📖 Kitap Listesi & Filtreler", "📲 Emanet İşlemleri"])

# --- 1. SEKME: YENİ KİTAP EKLE ---
with tab_ekle:
    st.subheader("Sisteme Yeni Kitap Ekle")
    c.execute("SELECT ad FROM kategoriler ORDER BY ad ASC")
    kategori_listesi = [row[0] for row in c.fetchall()]
    c.execute("SELECT DISTINCT yazar FROM kitaplar WHERE yazar != '' ORDER BY yazar ASC")
    mevcut_yazarlar = [row[0] for row in c.fetchall()]

    fk = st.session_state["form_key"]
    y_ad = st.text_input("Kitap Adı:", key=f"kitap_adi_{fk}")
    yazar_giris = st.text_input("Yazar Adı Soyadı:", key=f"yazar_adi_{fk}", placeholder="Yazmaya başlayın...")

    if yazar_giris.strip():
        arama_terim = yazar_giris.strip().lower()
        tahminler = [y for y in mevcut_yazarlar if arama_terim in y.lower()]
        if tahminler and (len(tahminler) > 1 or tahminler[0].lower() != arama_terim):
            st.caption("💡 Otomatik Tahminler:")
            cols = st.columns(min(len(tahminler), 3))
            for idx, t_yazar in enumerate(tahminler[:3]):
                if cols[idx % 3].button(t_yazar, key=f"tahmin_{idx}"):
                    st.session_state[f"yazar_adi_{fk}"] = t_yazar
                    st.rerun()

    y_kat = st.selectbox("Kitap Türü (Kategori):", kategori_listesi if kategori_listesi else ["Genel"])

    if st.button("Kitabı Kaydet", use_container_width=True):
        kaydedilecek_yazar = yazar_giris.strip()
        kaydedilecek_ad = y_ad.strip()

        if kaydedilecek_ad and kaydedilecek_yazar:
            c.execute("SELECT id FROM kitaplar WHERE LOWER(ad) = LOWER(?) AND LOWER(yazar) = LOWER(?)", (kaydedilecek_ad, kaydedilecek_yazar))
            if c.fetchone():
                st.error(f"⚠️ '{kaydedilecek_ad}' isimli kitap zaten kayıtlı!")
            else:
                c.execute("INSERT INTO kitaplar (ad, yazar, kategori, durum, emanet_alan, okundu_durum) VALUES (?, ?, ?, 'Kütüphanede', '', 'Okunmadı')", (kaydedilecek_ad, kaydedilecek_yazar, y_kat))
                conn.commit()
                st.session_state["form_key"] += 1
                st.toast(f"✅ '{kaydedilecek_ad}' eklendi!", icon="📚")
                st.rerun()
        else:
            st.warning("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")

# --- 2. SEKME: KİTAP LİSTESİ ---
with tab_liste:
    st.subheader("📖 Kitap Envanteri")
    excel_col1, excel_col2 = st.columns(2)

    try:
        c.execute("SELECT kategori AS Kategori, ad AS Isim, yazar AS Yazar, durum AS Durum, emanet_alan AS 'Emanet Alan', okundu_durum AS 'Okunma Durumu' FROM kitaplar ORDER BY id DESC")
        tum_kitaplar_raw = c.fetchall()
    except sqlite3.OperationalError:
        tum_kitaplar_raw = []

    if tum_kitaplar_raw:
        df_export = pd.DataFrame(tum_kitaplar_raw, columns=["Kategori", "Isim", "Yazar", "Durum", "Emanet Alan", "Okunma Durumu"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Kitap Listesi")
        excel_data = output.getvalue()
        excel_col1.download_button(label="📤 Excel Dışa Aktar", data=excel_data, file_name="Kutuphane_Kitap_Listesi.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    else:
        excel_col1.button("📤 Excel Dışa Aktar", disabled=True, use_container_width=True)

    with excel_col2:
        show_import = st.popover("📥 Excel İçe Aktar", use_container_width=True)
        with show_import:
            uploaded_file = st.file_uploader("Excel seçin", type=["xlsx", "xls", "xlsm"], label_visibility="collapsed", key="excel_uploader")
            if uploaded_file is not None:
                try:
                    excel_file = pd.ExcelFile(uploaded_file, engine="openpyxl")
                    selected_sheet = excel_file.sheet_names[0]
                    if st.button("Onayla ve Yükle", use_container_width=True):
                        with st.spinner("Aktarılıyor..."):
                            df_raw = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=None, engine="openpyxl")
                            kat_idx, isim_idx, yazar_idx = 0, 1, 2
                            header_row = 0
                            for r_idx in range(min(5, len(df_raw))):
                                row_vals = [str(val).strip().lower() for val in df_raw.iloc[r_idx].values]
                                for c_idx, val in enumerate(row_vals):
                                    if val in ["kategori", "tür", "tur"]: kat_idx = c_idx
                                    elif val in ["isim", "kitap adı", "kitap adi", "ad", "kitap"]: isim_idx = c_idx
                                    elif val in ["yazar", "yazar adı", "author"]: yazar_idx = c_idx
                                if "isim" in row_vals or "kitap adı" in row_vals or "ad" in row_vals:
                                    header_row = r_idx + 1
                                    break

                            conn_imp = get_db_connection()
                            c_imp = conn_imp.cursor()
                            c_imp.execute("SELECT LOWER(ad), LOWER(yazar) FROM kitaplar")
                            mevcut_set = set(c_imp.fetchall())
                            ekler = []
                            kategoriler_to_add = set()
                            atlanan = 0
                            yasakli_kelimeler = ["isim", "kitap adı", "kitap adi", "ad", "title", "yazar", "kategori", "tür", "durum", "emanet alan", "okunma durumu"]

                            for r_i in range(header_row, len(df_raw)):
                                row = df_raw.iloc[r_i]
                                kategori = str(row[kat_idx]).strip() if pd.notna(row[kat_idx]) else "Genel"
                                ad = str(row[isim_idx]).strip() if pd.notna(row[isim_idx]) else ""
                                yazar = str(row[yazar_idx]).strip() if pd.notna(row[yazar_idx]) else ""

                                if ad.lower() in yasakli_kelimeler or yazar.lower() in yasakli_kelimeler: continue
                                if ad and yazar and ad.lower() != "nan" and yazar.lower() != "nan":
                                    if (ad.lower(), yazar.lower()) in mevcut_set: atlanan += 1
                                    else:
                                        ekler.append((ad, yazar, kategori, "Kütüphanede", "", "Okunmadı"))
                                        kategoriler_to_add.add(kategori)
                                        mevcut_set.add((ad.lower(), yazar.lower()))

                            if kategoriler_to_add:
                                c_imp.executemany("INSERT OR IGNORE INTO kategoriler (ad) VALUES (?)", [(str(k),) for k in kategoriler_to_add])
                            if ekler:
                                c_imp.executemany("INSERT INTO kitaplar (ad, yazar, kategori, durum, emanet_alan, okundu_durum) VALUES (?, ?, ?, ?, ?, ?)", ekler)
                            conn_imp.commit()
                            conn_imp.close()
                            st.success(f"🎉 {len(ekler)} kitap aktarıldı, {atlanan} mükerrer atlandı.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")

    with st.expander("🔍 Detaylı Filtreleme ve Arama", expanded=False):
        col1, col2 = st.columns(2)
        with col1: arama_metin = st.text_input("Kitap / Yazar Ara")
        with col2:
            c.execute("SELECT ad FROM kategoriler ORDER BY ad ASC")
            turler_filtre = ["Tümü"] + [row[0] for row in c.fetchall()]
            f_tur = st.selectbox("Tür Filtresi", turler_filtre)
        col3, col4 = st.columns(2)
        with col3:
            c.execute("SELECT DISTINCT yazar FROM kitaplar WHERE yazar != '' ORDER BY yazar ASC")
            yazarlar_filtre = ["Tümü"] + [row[0] for row in c.fetchall()]
            f_yazar = st.selectbox("Yazar Filtresi", yazarlar_filtre)
        with col4: f_okundu = st.selectbox("Okunma Durumu", ["Tümü", "Okundu", "Okunmadı"])

    sorgu = "SELECT id, ad, yazar, kategori, durum, emanet_alan, okundu_durum FROM kitaplar WHERE 1=1"
    params = []
    if arama_metin:
        sorgu += " AND (ad LIKE ? OR yazar LIKE ?)"
        params.extend([f"%{arama_metin}%", f"%{arama_metin}%"])
    if f_tur != "Tümü":
        sorgu += " AND kategori = ?"
        params.append(f_tur)
    if f_yazar != "Tümü":
        sorgu += " AND yazar = ?"
        params.append(f_yazar)
    if f_okundu != "Tümü":
        sorgu += " AND okundu_durum = ?"
        params.append(f_okundu)

    c.execute(sorgu, params)
    kitaplar = c.fetchall()
    st.divider()

    if kitaplar:
        for k in kitaplar:
            k_id, k_ad, k_yazar, k_kat, k_durum, k_emanet, k_okundu = k
            with st.expander(f"📘 {k_ad}"):
                col_detay, col_qr = st.columns([2, 1.2])
                with col_detay:
                    st.write(f"**ID:** #{k_id}")
                    st.write(f"**Yazar:** {k_yazar}")
                    st.write(f"**Tür:** {k_kat}")
                    if k_durum == "Emanette": st.error(f"🔴 Emanette: {k_emanet}")
                    else: st.success("🟢 Kütüphanede")

                    is_okundu = bool(str(k_okundu) == "Okundu")
                    btn_label = "✅ Okundu (Okunmadı Yap)" if is_okundu else "📖 Okunmadı (Okundu Yap)"
                    if st.button(btn_label, key=f"btn_okundu_{k_id}", use_container_width=True):
                        yeni_durum = "Okunmadı" if is_okundu else "Okundu"
                        c.execute("UPDATE kitaplar SET okundu_durum = ? WHERE id = ?", (yeni_durum, k_id))
                        conn.commit()
                        st.toast(f"#{k_id} güncellendi!")
                        st.rerun()

                    if st.button("🗑️ Kitabı Sil", key=f"btn_sil_{k_id}", use_container_width=True):
                        c.execute("DELETE FROM kitaplar WHERE id = ?", (k_id,))
                        conn.commit()
                        st.toast(f"🗑️ '{k_ad}' silindi!")
                        st.rerun()

                with col_qr:
                    qr_data = f"KITAP_ID:{k_id} - {k_ad}"
                    encoded_qr_data = urllib.parse.quote(qr_data)
                    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_qr_data}"
                    st.image(qr_url, caption=f"ID: #{k_id}", width=150)
    else:
        st.info("Kriterlere uygun kitap bulunamadı.")

# --- 3. SEKME: EMANET İŞLEMLERİ ---
with tab_emanet:
    st.subheader("📲 Emanet / Teslim İşlemleri")

    # --- EMANETTEKİ KİTAPLAR LİSTESİ ---
    c.execute("SELECT id, ad, yazar, kategori, emanet_alan FROM kitaplar WHERE durum = 'Emanette' ORDER BY id DESC")
    emanetteki_kitaplar = c.fetchall()

    with st.expander(f"🔴 Emanetteki Kitaplar ({len(emanetteki_kitaplar)})", expanded=False):
        if emanetteki_kitaplar:
            for ek in emanetteki_kitaplar:
                ek_id, ek_ad, ek_yazar, ek_kat, ek_alan = ek
                with st.expander(f"📖 {ek_ad} (Kişi: {ek_alan})"):
                    st.write(f"**ID:** #{ek_id}")
                    st.write(f"**Yazar:** {ek_yazar}")
                    st.write(f"**Tür:** {ek_kat}")
                    st.write(f"**Emanet Alan Kişi:** {ek_alan}")
                    if st.button("📥 Kütüphaneye Geri Al", key=f"btn_list_geri_al_{ek_id}", use_container_width=True):
                        c.execute("UPDATE kitaplar SET durum = 'Kütüphanede', emanet_alan = '' WHERE id = ?", (ek_id,))
                        conn.commit()
                        st.toast(f"✅ '{ek_ad}' geri alındı!")
                        emanet_sifirla()
                        st.rerun()
        else:
            st.info("Şu an emanette hiçbir kitap bulunmuyor.")

    st.markdown("---")
    ek_key = st.session_state["emanet_key"]

    islem_tipi = st.radio("Yapmak İstediğiniz İşlem:", ["Emanet Ver", "Emanetten Geri Al"], horizontal=True, key=f"radio_islem_{ek_key}")

    if islem_tipi == "Emanet Ver":
        c.execute("SELECT id, ad, yazar FROM kitaplar WHERE durum = 'Kütüphanede' ORDER BY ad ASC")
        uygun_kitaplar = c.fetchall()
    else:
        c.execute("SELECT id, ad, emanet_alan FROM kitaplar WHERE durum = 'Emanette' ORDER BY ad ASC")
        uygun_kitaplar = c.fetchall()

    secilen_kitap_id = None
    if uygun_kitaplar:
        if islem_tipi == "Emanet Ver": options_dict = {f"#{k[0]} - {k[1]} ({k[2]})": k[0] for k in uygun_kitaplar}
        else: options_dict = {f"#{k[0]} - {k[1]} (Emanette: {k[2]})": k[0] for k in uygun_kitaplar}
        
        default_index = 0
        if st.session_state["scanned_id"] is not None:
            for idx, k_id_val in enumerate(options_dict.values()):
                if k_id_val == st.session_state["scanned_id"]:
                    default_index = idx
                    break
                    
        secilen_label = st.selectbox("Listeden Kitap Seçin:", list(options_dict.keys()), index=default_index, key=f"select_kitap_{ek_key}")
        secilen_kitap_id = options_dict[secilen_label]
    else:
        if islem_tipi == "Emanet Ver": st.info("Emanet verilebilecek uygun kitap yok.")
        else: st.info("Şu an emanette kitap yok.")

    with st.expander("veya Manuel / QR ile ID Girin"):
        default_val = st.session_state["scanned_id"] if st.session_state["scanned_id"] is not None else 1
        kitap_id_manual = st.number_input("Kitap ID:", min_value=1, step=1, value=int(default_val), key=f"input_manual_id_{ek_key}")
        if st.button("Bu ID'yi Kullan", key=f"btn_id_kullan_{ek_key}"): secilen_kitap_id = kitap_id_manual

    if not st.session_state["kamera_acik"]:
        if st.button("📷 QR Kamerasını Aç", use_container_width=True, key=f"btn_cam_open_{ek_key}"):
            st.session_state["kamera_acik"] = True
            st.rerun()
    else:
        if st.button("❌ Kamerayı Kapat", use_container_width=True, key=f"btn_cam_close_{ek_key}"):
            st.session_state["kamera_acik"] = False
            st.rerun()

        cam_k = st.session_state["camera_key"]
        kamera_foto = st.camera_input("QR Kodu Taramak İçin Fotoğraf Çekin", key=f"camera_input_{cam_k}")
        if kamera_foto is not None:
            bytes_data = kamera_foto.getvalue()
            np_img = np.frombuffer(bytes_data, np.uint8)
            img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            detector = cv2.QRCodeDetector()
            decoded_info, points, _ = detector.detectAndDecode(img)
            if decoded_info:
                match = re.search(r"KITAP_ID:(\d+)", decoded_info)
                if match:
                    found_id = int(match.group(1))
                    st.session_state["scanned_id"] = found_id
                    st.session_state["kamera_acik"] = False
                    st.toast(f"🎯 QR Kod Okundu! ID: #{found_id}", icon="✅")
                    st.rerun()
                else: st.warning("Geçerli bir Kitap ID bulunamadı.")
            else: st.error("⚠️ QR Kod tespit edilemedi.")

    st.markdown("---")
    kisi_adi = ""
    if islem_tipi == "Emanet Ver":
        kisi_adi = st.text_input("Emanet Edilecek Kişinin Adı Soyadı:", key=f"kisi_adi_{ek_key}")

    if st.button("İşlemi Onayla ve Kaydet", use_container_width=True, key=f"btn_onayla_{ek_key}"):
        if secilen_kitap_id is None:
            st.warning("Lütfen işlem yapılacak bir kitap seçin.")
        else:
            c.execute("SELECT id, ad, yazar, durum, emanet_alan FROM kitaplar WHERE id = ?", (secilen_kitap_id,))
            kitap = c.fetchone()
            if not kitap:
                st.error(f"#{secilen_kitap_id} ID'li bir kitap bulunamadı.")
            else:
                k_id, ad, yazar, mevc_durum, mevc_emanet = kitap
                if islem_tipi == "Emanet Ver":
                    if mevc_durum == "Emanette":
                        st.error(f"Bu kitap zaten {mevc_emanet} kişisinde!")
                    elif not kisi_adi.strip():
