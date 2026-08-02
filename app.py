import io
import re
import sqlite3
import urllib.parse
import urllib.request
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# Sayfa Yapılandırması
st.set_page_config(
    page_title="Kütüphane Yönetimi", page_icon="📚", layout="centered"
)

# --- ÖZEL KREM / HAKİ / SİYAH TEMA (CSS) ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #F5F2EB;
        color: #1A1A1A;
    }
    
    h1, h2, h3, h4, h5, h6, label, p, span {
        color: #2C3022 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* SEKMELER: HAKİ ARKA PLAN & KREM YAZI */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #4A5335 !important;
        border-radius: 8px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #F5F2EB !important;
        font-weight: bold;
    }

    .stTabs [aria-selected="true"] {
        background-color: #353B26 !important;
        color: #FFFFFF !important;
        border-radius: 6px;
    }

    .stButton>button, .stDownloadButton>button {
        background-color: #4A5335 !important;
        color: #F5F2EB !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        transition: 0.3s;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        background-color: #353B26 !important;
        color: #FFFFFF !important;
    }

    input, select, textarea, div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border-radius: 6px !important;
    }
    
    div[data-testid="stExpander"] {
        background-color: #EAE5D9;
        border: 1px solid #D6CEBE;
        border-radius: 8px;
        margin-bottom: 8px;
    }

    [data-testid="stMetricValue"] {
        color: #4A5335 !important;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- QR KOD VE İSİM BİRLEŞTİRME FONKSİYONU ---
def generate_labeled_qr(qr_url, book_title):
    req = urllib.request.Request(qr_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        qr_img = Image.open(io.BytesIO(response.read())).convert("RGB")

    qr_w, qr_h = qr_img.size
    text_padding = 40
    new_h = qr_h + text_padding

    final_img = Image.new("RGB", (qr_w, new_h), "white")
    final_img.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(final_img)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), book_title, font=font)
    text_w = bbox[2] - bbox[0]
    x = (qr_w - text_w) / 2
    y = qr_h + (text_padding - (bbox[3] - bbox[1])) / 2 - 4

    draw.text((x, y), book_title, fill="black", font=font)

    img_byte_arr = io.BytesIO()
    final_img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


# --- EXCEL OLUŞTURMA FONKSİYONU (BYTES) ---
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Kitap Listesi")
    return output.getvalue()


# --- VERİTABANI BAĞLANTISI VE KİLİTLENME ÖNLEME ---
def get_db_connection():
    conn = sqlite3.connect("kutuphane.db", timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass
    return conn


# Ana Kurulum İşlemleri
conn = get_db_connection()
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS kitaplar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    yazar TEXT NOT NULL,
    kategori TEXT,
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

# Eksik sütun kontrolü ve eklenmesi (Migrasyon)
c.execute("PRAGMA table_info(kitaplar)")
mevcut_sutunlar = [col[1] for col in c.fetchall()]

if "durum" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN durum TEXT DEFAULT 'Kütüphanede'")
if "emanet_alan" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN emanet_alan TEXT DEFAULT ''")
if "okundu_durum" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN okundu_durum TEXT DEFAULT 'Okunmadı'")

conn.commit()

# Varsayılan kategoriler
c.execute("SELECT COUNT(*) FROM kategoriler")
if c.fetchone()[0] == 0:
    varsayilan_kategoriler = [
        ("Roman",),
        ("Tarih",),
        ("Felsefe",),
        ("Bilim",),
        ("Kişisel Gelişim",),
    ]
    c.executemany(
        "INSERT INTO kategoriler (ad) VALUES (?)" , varsayilan_kategoriler
    )
    conn.commit()

# --- BAŞLIK VE SAYI ÖZETLERİ ---
st.title("📚 Kütüphane Yönetim Sistemi")

c.execute("SELECT COUNT(*) FROM kitaplar")
toplam_kitap = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM kitaplar WHERE durum = 'Emanette'")
emanette_kitap = c.fetchone()[0]

m_col1, m_col2 = st.columns(2)
m_col1.metric(label="📖 Toplam Kitap Sayısı", value=toplam_kitap)
m_col2.metric(label="🔴 Emanetteki Kitap Sayısı", value=emanette_kitap)

st.divider()

if "form_key" not in st.session_state:
    st.session_state["form_key"] = 0

if "kamera_acik" not in st.session_state:
    st.session_state["kamera_acik"] = False

if "scanned_id" not in st.session_state:
    st.session_state["scanned_id"] = 1

# --- SEKMELER ---
tab_ekle, tab_liste, tab_emanet = st.tabs(
    ["➕ Yeni Kitap Ekle", "📖 Kitap Listesi & Filtreler", "📲 Emanet İşlemleri"]
)

# ==========================================
# 1. SEKME: YENİ KİTAP EKLE
# ==========================================
with tab_ekle:
    st.subheader("Sisteme Yeni Kitap Ekle")

    c.execute("SELECT ad FROM kategoriler ORDER BY ad ASC")
    kategori_listesi = [row[0] for row in c.fetchall()]

    c.execute(
        "SELECT DISTINCT yazar FROM kitaplar WHERE yazar != '' ORDER BY yazar ASC"
    )
    mevcut_yazarlar = [row[0] for row in c.fetchall()]

    fk = st.session_state["form_key"]

    y_ad = st.text_input("Kitap Adı:", key=f"kitap_adi_{fk}")

    yazar_giris = st.text_input(
        "Yazar Adı Soyadı:",
        key=f"yazar_adi_{fk}",
        placeholder="Yazmaya başlayın...",
    )

    if yazar_giris.strip():
        arama_terim = yazar_giris.strip().lower()
        tahminler = [y for y in mevcut_yazarlar if arama_terim in y.lower()]

        if tahminler and (
            len(tahminler) > 1 or tahminler[0].lower() != arama_terim
        ):
            st.caption("💡 Otomatik Tahminler (Tıklayarak Seçebilirsiniz):")
            cols = st.columns(min(len(tahminler), 3))
            for idx, t_yazar in enumerate(tahminler[:3]):
                if cols[idx % 3].button(t_yazar, key=f"tahmin_{idx}"):
                    st.session_state[f"yazar_adi_{fk}"] = t_yazar
                    st.rerun()

    y_kat = st.selectbox("Kitap Türü (Kategori):", kategori_listesi)

    if st.button("Kitabı Kaydet", use_container_width=True):
        kaydedilecek_yazar = yazar_giris.strip()
        kaydedilecek_ad = y_ad.strip()

        if kaydedilecek_ad and kaydedilecek_yazar:
            c.execute(
                "SELECT id FROM kitaplar WHERE LOWER(ad) = LOWER(?) AND LOWER(yazar) = LOWER(?)",
                (kaydedilecek_ad, kaydedilecek_yazar),
            )
            if c.fetchone():
                st.error(
                    f"⚠️ **Uyarı:** '{kaydedilecek_ad}' isimli kitap **{kaydedilecek_yazar}** yazarı ile zaten kayıtlı!"
                )
            else:
                c.execute(
                    """
                    INSERT INTO kitaplar (ad, yazar, kategori, durum, emanet_alan, okundu_durum) 
                    VALUES (?, ?, ?, 'Kütüphanede', '', 'Okunmadı')
                    """,
                    (kaydedilecek_ad, kaydedilecek_yazar, y_kat),
                )
                conn.commit()

                st.session_state["form_key"] += 1
                st.toast(
                    f"✅ '{kaydedilecek_ad}' kütüphaneye başarıyla eklendi!", icon="📚"
                )
                st.rerun()
        else:
            st.warning("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")

# ==========================================
# 2. SEKME: KİTAP LİSTESİ VE FİLTRELER
# ==========================================
with tab_liste:
    st.subheader("📖 Kitap Envanteri")

    excel_col1, excel_col2 = st.columns(2)

    # Dışa Aktarma
    try:
        c.execute(
            "SELECT kategori AS Kategori, ad AS Isim, yazar AS Yazar, durum AS Durum, "
            "emanet_alan AS 'Emanet Alan', okundu_durum AS 'Okunma Durumu' "
            "FROM kitaplar ORDER BY id DESC"
        )
        tum_kitaplar_raw = c.fetchall()
    except sqlite3.OperationalError:
        tum_kitaplar_raw = []

    if tum_kitaplar_raw:
        df_export = pd.DataFrame(
            tum_kitaplar_raw,
            columns=[
                "Kategori",
                "Isim",
                "Yazar",
                "Durum",
                "Emanet Alan",
                "Okunma Durumu",
            ],
        )
        excel_data = convert_df_to_excel(df_export)

        excel_col1.download_button(
            label="📤 Excel Dışa Aktar",
            data=excel_data,
            file_name="Kutuphane_Kitap_Listesi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        excel_col1.button("📤 Excel Dışa Aktar", disabled=True, use_container_width=True)

    # İçe Aktarma (GÜVENLİ VE AKILLI SÜTUN ALGINALAYICI)
    with excel_col2:
        show_import = st.popover("📥 Excel İçe Aktar", use_container_width=True)
        with show_import:
            st.markdown("**Excel'den Kitap Yükle**")
            
            uploaded_file = st.file_uploader(
                "Excel seçin",
                type=["xlsx", "xls", "xlsm"],
                label_visibility="collapsed",
            )

            if uploaded_file is not None:
                try:
                    excel_file = pd.ExcelFile(uploaded_file, engine="openpyxl")
                    sheet_names = excel_file.sheet_names

                    if len(sheet_names) > 1:
                        selected_sheet = st.selectbox("📂 Okunacak Sayfayı Seçin:", sheet_names)
                    else:
                        selected_sheet = sheet_names[0]

                    if st.button("Onayla ve Yükle", use_container_width=True):
                        # Dosyayı ham haliyle header'sız oku
                        df_raw = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=None, engine="openpyxl")
                        
                        kat_idx, isim_idx, yazar_idx = None, None, None
                        header_row = 0

                        # İlk 5 satırda başlık kelimelerini tara
                        for r_idx in range(min(5, len(df_raw))):
                            row_vals = [str(val).strip().lower() for val in df_raw.iloc[r_idx].values]
                            for c_idx, val in enumerate(row_vals):
                                if val in ["kategori", "tür", "tur", "category"]:
                                    kat_idx = c_idx
                                elif val in ["isim", "kitap adı", "kitap adi", "ad", "title", "book", "kitap"]:
                                    isim_idx = c_idx
                                elif val in ["yazar", "yazar adı", "yazar adi", "author"]:
                                    yazar_idx = c_idx
                            
                            if kat_idx is not None and isim_idx is not None and yazar_idx is not None:
                                header_row = r_idx + 1
                                break

                        # Eğer başlıklar bulunamadıysa varsayılan 0: Kategori, 1: Isim, 2: Yazar kabul et
                        if kat_idx is None or isim_idx is None or yazar_idx is None:
                            kat_idx = 0 if df_raw.shape[1] > 0 else None
                            isim_idx = 1 if df_raw.shape[1] > 1 else None
                            yazar_idx = 2 if df_raw.shape[1] > 2 else None
                            header_row = 0

                        if kat_idx is not None and isim_idx is not None and yazar_idx is not None:
                            eklenen = 0
                            atlanan = 0

                            conn_imp = get_db_connection()
                            c_imp = conn_imp.cursor()

                            for r_i in range(header_row, len(df_raw)):
                                row = df_raw.iloc[r_i]
                                kategori = str(row[kat_idx]).strip() if pd.notna(row[kat_idx]) else "Genel"
                                ad = str(row[isim_idx]).strip() if pd.notna(row[isim_idx]) else ""
                                yazar = str(row[yazar_idx]).strip() if pd.notna(row[yazar_idx]) else ""

                                # Başlık kelimeleri denk geldiyse atla
                                if ad.lower() in ["isim", "kitap adı", "ad", "title"] and yazar.lower() in ["yazar", "author"]:
                                    continue

                                if ad and yazar and ad.lower() != "nan" and yazar.lower() != "nan":
                                    c_imp.execute(
                                        "SELECT id FROM kitaplar WHERE LOWER(ad) = LOWER(?) AND LOWER(yazar) = LOWER(?)",
                                        (ad, yazar),
                                    )
                                    if c_imp.fetchone():
                                        atlanan += 1
                                    else:
                                        c_imp.execute(
                                            "INSERT OR IGNORE INTO kategoriler (ad) VALUES (?)",
                                            (kategori,),
                                        )
                                        c_imp.execute(
                                            """
                                            INSERT INTO kitaplar (ad, yazar, kategori, durum, emanet_alan, okundu_durum) 
                                            VALUES (?, ?, ?, 'Kütüphanede', '', 'Okunmadı')
                                            """,
                                            (ad, yazar, kategori),
                                        )
                                        eklenen += 1

                            conn_imp.commit()
                            conn_imp.close()

                            st.toast(f"🎉 {eklenen} kitap eklendi, {atlanan} mükerrer kayıt atlandı.")
                            st.rerun()
                        else:
                            st.error("⚠️ Excel dosyasında uygun Kategori, İsim ve Yazar alanları tespit edilemedi.")
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")

    # --- FİLTRELER ---
    with st.expander("🔍 Detaylı Filtreleme ve Arama", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            arama_metin = st.text_input("Kitap / Yazar Ara")
        with col2:
            c.execute("SELECT ad FROM kategoriler ORDER BY ad ASC")
            turler_filtre = ["Tümü"] + [row[0] for row in c.fetchall()]
            f_tur = st.selectbox("Tür Filtresi", turler_filtre)

        col3, col4 = st.columns(2)
        with col3:
            c.execute("SELECT DISTINCT yazar FROM kitaplar ORDER BY yazar ASC")
            yazarlar_filtre = ["Tümü"] + [row[0] for row in c.fetchall()]
            f_yazar = st.selectbox("Yazar Filtresi", yazarlar_filtre)
        with col4:
            f_okundu = st.selectbox(
                "Okunma Durumu", ["Tümü", "Okundu", "Okunmadı"]
            )

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

                    if k_durum == "Emanette":
                        st.error(f"🔴 Emanette: {k_emanet}")
                    else:
                        st.success("🟢 Kütüphanede")

                    is_okundu = k_okundu == "Okundu"
                    btn_label = (
                        "✅ Okundu (Okunmadı Yap)"
                        if is_okundu
                        else "📖 Okunmadı (Okundu Yap)"
                    )

                    if st.button(
                        btn_label, key=f"btn_okundu_{k_id}", use_container_width=True
                    ):
                        yeni_durum = "Okunmadı" if is_okundu else "Okundu"
                        c.execute(
                            "UPDATE kitaplar SET okundu_durum = ? WHERE id = ?",
                            (yeni_durum, k_id),
                        )
                        conn.commit()
                        st.toast(
                            f"#{k_id} '{k_ad}' durumu '{yeni_durum}' olarak güncellendi!"
                        )
                        st.rerun()

                with col_qr:
                    qr_data = f"KITAP_ID:{k_id} - {k_ad}"
                    encoded_qr_data = urllib.parse.quote(qr_data)
                    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_qr_data}"

                    try:
                        labeled_qr_bytes = generate_labeled_qr(qr_url, k_ad)

                        st.image(
                            labeled_qr_bytes,
                            caption=f"ID: #{k_id}",
                            use_container_width=True,
                        )

                        st.download_button(
                            label="📥 QR İndir (.png)",
                            data=labeled_qr_bytes,
                            file_name=f"QR_{k_ad.replace(' ', '_')}.png",
                            mime="image/png",
                            key=f"dl_qr_{k_id}",
                            use_container_width=True,
                        )
                    except Exception:
                        st.caption("QR görseli oluşturulamadı.")

    else:
        st.info("Kriterlere uygun kitap bulunamadı.")

    # --- TÜRLERİ YÖNETME ---
    st.write("---")
    with st.expander("⚙️ Kitap Türü (Kategori) Ayarları"):
        c.execute("SELECT id, ad FROM kategoriler ORDER BY ad ASC")
        kategoriler = c.fetchall()

        yeni_tur = st.text_input("Yeni Tür Adı:")
        if st.button("Tür Ekle"):
            if yeni_tur.strip():
                try:
                    c.execute(
                        "INSERT INTO kategoriler (ad) VALUES (?)", (yeni_tur.strip(),)
                    )
                    conn.commit()
                    st.toast(f"'{yeni_tur}' türü eklendi!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("Bu tür zaten mevcut.")
            els
