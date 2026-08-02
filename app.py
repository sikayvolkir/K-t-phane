import sqlite3
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

    .stButton>button {
        background-color: #4A5335 !important;
        color: #F5F2EB !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
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
    }

    [data-testid="stMetricValue"] {
        color: #4A5335 !important;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- VERİTABANI BAĞLANTISI ---
conn = sqlite3.connect("kutuphane.db", check_same_thread=False)
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

try:
  c.execute("SELECT okundu_durum FROM kitaplar LIMIT 1")
except sqlite3.OperationalError:
  c.execute("DROP TABLE IF EXISTS kitaplar")
  c.execute("""
    CREATE TABLE kitaplar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        yazar TEXT NOT NULL,
        kategori TEXT,
        durum TEXT DEFAULT 'Kütüphanede',
        emanet_alan TEXT DEFAULT '',
        okundu_durum TEXT DEFAULT 'Okunmadı'
    )
    """)

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
      "INSERT INTO kategoriler (ad) VALUES (?)", varsayilan_kategoriler
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

# Session State Hazırlıkları
if "yazar_input" not in st.session_state:
  st.session_state["yazar_input"] = ""
if "kitap_adi_input" not in st.session_state:
  st.session_state["kitap_adi_input"] = ""

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

  y_ad = st.text_input("Kitap Adı:", key="kitap_adi_input")

  # DİNAMİK YAZAR GİRİŞİ
  yazar_giris = st.text_input(
      "Yazar Adı Soyadı:",
      key="yazar_input",
      placeholder="Yazmaya başlayın (Örn: İsmet Özel)...",
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
          st.session_state["yazar_input"] = t_yazar
          st.rerun()

  y_kat = st.selectbox("Kitap Türü (Kategori):", kategori_listesi)

  if st.button("Kitabı Kaydet", use_container_width=True):
    kaydedilecek_yazar = yazar_giris.strip()
    kaydedilecek_ad = y_ad.strip()

    if kaydedilecek_ad and kaydedilecek_yazar:
      c.execute(
          "SELECT id FROM kitaplar WHERE LOWER(ad) = LOWER(?) AND LOWER(yazar)"
          " = LOWER(?)",
          (kaydedilecek_ad, kaydedilecek_yazar),
      )
      if c.fetchone():
        st.error(
            f"⚠️ **Uyarı:** '{kaydedilecek_ad}' isimli kitap"
            f" **{kaydedilecek_yazar}** yazarı ile zaten kayıtlı!"
        )
      else:
        c.execute(
            """
                    INSERT INTO kitaplar (ad, yazar, kategori, okundu_durum) 
                    VALUES (?, ?, ?, 'Okunmadı')
                """,
            (kaydedilecek_ad, kaydedilecek_yazar, y_kat),
        )
        conn.commit()

        # Ekranı temizle
        st.session_state["kitap_adi_input"] = ""
        st.session_state["yazar_input"] = ""

        # Bildirim Göster ve Yenile
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

  with st.expander("🔍 Detaylı Filtreleme ve Arama", expanded=True):
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

  sorgu = "SELECT * FROM kitaplar WHERE 1=1"
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
      with st.container():
        c_left, c_right = st.columns([2.5, 1.5])
        with c_left:
          st.markdown(f"### #{k_id} - {k_ad}")
          st.write(f"**Yazar:** {k_yazar} | **Tür:** {k_kat}")
          if k_durum == "Emanette":
            st.error(f"🔴 Emanette: {k_emanet}")
          else:
            st.success("🟢 Kütüphanede")

        with c_right:
          is_okundu = k_okundu == "Okundu"
          btn_label = "✅ Okundu" if is_okundu else "📖 Okunmadı"

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

        st.divider()
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
      else:
        st.warning("Lütfen bir tür adı girin.")

    st.write("---")
    if kategoriler:
      silinecek_tur = st.selectbox(
          "Silinecek Türü Seçin:", [k[1] for k in kategoriler]
      )
      if st.button("Seçili Türü Sil"):
        c.execute("DELETE FROM kategoriler WHERE ad = ?", (silinecek_tur,))
        conn.commit()
        st.toast(f"'{silinecek_tur}' türü silindi!")
        st.rerun()

# ==========================================
# 3. SEKME: EMANET İŞLEMLERİ & QR
# ==========================================
with tab_emanet:
  st.subheader("📲 QR Kamera ile Emanet / Teslim")

  islem_tipi = st.radio(
      "Yapmak İstediğiniz İşlem:",
      ["Emanet Ver", "Emanetten Geri Al"],
      horizontal=True,
  )

  kitap_id_manual = st.number_input(
      "Kitap ID (Veya QR Kamera Açın):", min_value=1, step=1
  )
  kamera_foto = st.camera_input("QR Kodu Taramak İçin Kamerayı Açın")

  kisi_adi = ""
  if islem_tipi == "Emanet Ver":
    kisi_adi = st.text_input("Emanet Edilecek Kişinin Adı Soyadı:")

  if st.button("İşlemi Onayla ve Kaydet", use_container_width=True):
    c.execute("SELECT * FROM kitaplar WHERE id = ?", (kitap_id_manual,))
    kitap = c.fetchone()

    if kitap:
      k_id, ad, yazar, kat, durum, emanet_alan, okundu = kitap

      if islem_tipi == "Emanet Ver":
        if durum == "Emanette":
          st.error(f"Bu kitap zaten **{emanet_alan}** isimli kişide!")
        elif not kisi_adi.strip():
          st.warning("Lütfen kitabı alacak kişinin adını girin.")
        else:
          c.execute(
              "UPDATE kitaplar SET durum = 'Emanette', emanet_alan = ? WHERE"
              " id = ?",
              (kisi_adi.strip(), k_id),
          )
          conn.commit()
          st.toast(f"✅ '{ad}' kitabı **{kisi_adi}** kişisine verildi!")
          st.rerun()

      elif islem_tipi == "Emanetten Geri Al":
        if durum == "Kütüphanede":
          st.info("Bu kitap zaten kütüphanede görünüyor.")
        else:
          c.execute(
              "UPDATE kitaplar SET durum = 'Kütüphanede', emanet_alan = ''"
              " WHERE id = ?",
              (k_id,),
          )
          conn.commit()
          st.toast(f"✅ '{ad}' kitabı kütüphaneye teslim alındı!")
          st.rerun()
    else:
      st.error("Bu ID'ye sahip bir kitap bulunamadı.")
        
