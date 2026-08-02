import sqlite3
import streamlit as st

# Sayfa Yapılandırması
st.set_page_config(
    page_title="Kütüphane Yönetimi", page_icon="📚", layout="centered"
)

# --- VERİTABANI BAĞLANTISI ---
conn = sqlite3.connect("kutuphane.db", check_same_thread=False)
c = conn.cursor()

# Eski uyumsuz tablo varsa kaldırıp temiz tablo oluşturalım (Hatayı çözen kısım)
c.execute("""
CREATE TABLE IF NOT EXISTS kitaplar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    yazar TEXT NOT NULL,
    kategori TEXT,
    durum TEXT DEFAULT 'Kütüphanede',
    emanet_alan TEXT DEFAULT ''
)
""")
conn.commit()

# Mevcut tabloda eksik sütun kontrolü (Garantili Çözüm)
try:
  c.execute("SELECT durum, emanet_alan FROM kitaplar LIMIT 1")
except sqlite3.OperationalError:
  # Eğer sütunlar eksikse tabloyu baştan temizce kur
  c.execute("DROP TABLE IF EXISTS kitaplar")
  c.execute("""
    CREATE TABLE kitaplar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        yazar TEXT NOT NULL,
        kategori TEXT,
        durum TEXT DEFAULT 'Kütüphanede',
        emanet_alan TEXT DEFAULT ''
    )
    """)
  conn.commit()

st.title("📚 Kütüphane Yönetim Sistemi")

# --- SEKMELER (TABS) ---
tab_emanet, tab_liste, tab_ekle = st.tabs(
    ["📲 Emanet / Teslim", "📖 Kitap Listesi", "➕ Yeni Kitap Ekle"]
)

# ==========================================
# 1. SEKME: EMANET VE TESLİM İŞLEMLERİ
# ==========================================
with tab_emanet:
  st.subheader("Kitap Teslim / Emanet Kaydı")

  kitap_id_input = st.number_input(
      "Kitap ID / QR Kodu Numarası:", min_value=1, step=1
  )
  st.camera_input("QR Kod Taraması (Kamera)")

  if st.button("Kitabı Sorgula"):
    c.execute("SELECT * FROM kitaplar WHERE id = ?", (kitap_id_input,))
    kitap = c.fetchone()

    if kitap:
      k_id, ad, yazar, kategori, durum, emanet_alan = kitap
      st.info(
          f"**Kitap Adı:** {ad}\n\n**Yazar:** {yazar}\n\n**Mevcut Durum:**"
          f" {durum}"
      )

      if durum == "Emanette":
        st.warning(f"Bu kitap şu an **{emanet_alan}** isimli kişide.")
        if st.button("Kitabı Geri Teslim Al"):
          c.execute(
              "UPDATE kitaplar SET durum = 'Kütüphanede', emanet_alan = ''"
              " WHERE id = ?",
              (k_id,),
          )
          conn.commit()
          st.success("Kitap başarıyla kütüphaneye teslim alındı!")
          st.rerun()
      else:
        kisi = st.text_input("Emanet Alacak Kişinin Adı Soyadı:")
        if st.button("Emanet Ver"):
          if kisi.strip():
            c.execute(
                "UPDATE kitaplar SET durum = 'Emanette', emanet_alan = ? WHERE"
                " id = ?",
                (kisi, k_id),
            )
            conn.commit()
            st.success(f"Kitap **{kisi}** kişisine teslim edildi!")
            st.rerun()
          else:
            st.error("Lütfen teslim edilecek kişinin adını girin.")
    else:
      st.error("Bu ID'ye ait kayıtlı kitap bulunamadı.")

# ==========================================
# 2. SEKME: KİTAP LİSTESİ VE ARAMA
# ==========================================
with tab_liste:
  st.subheader("Kitap Envanteri & Arama")

  col1, col2 = st.columns(2)
  with col1:
    arama = st.text_input("🔍 Kitap / Yazar Ara")
  with col2:
    durum_filtre = st.selectbox(
        "Durum Filtresi", ["Tümü", "Kütüphanede", "Emanette"]
    )

  sorgu = "SELECT * FROM kitaplar WHERE 1=1"
  params = []

  if arama:
    sorgu += " AND (ad LIKE ? OR yazar LIKE ?)"
    params.extend([f"%{arama}%", f"%{arama}%"])

  if durum_filtre != "Tümü":
    sorgu += " AND durum = ?"
    params.append(durum_filtre)

  c.execute(sorgu, params)
  kitaplar = c.fetchall()

  if kitaplar:
    for k in kitaplar:
      k_id, k_ad, k_yazar, k_kat, k_durum, k_emanet = k
      with st.container():
        st.markdown(f"### #{k_id} - {k_ad}")
        st.write(f"**Yazar:** {k_yazar} | **Kategori:** {k_kat}")
        if k_durum == "Emanette":
          st.error(f"🔴 Emanette: {k_emanet}")
        else:
          st.success("🟢 Kütüphanede")
        st.divider()
  else:
    st.info("Kayıtlı kitap bulunamadı.")

# ==========================================
# 3. SEKME: YENİ KİTAP EKLEME
# ==========================================
with tab_ekle:
  st.subheader("Sisteme Yeni Kitap Ekle")
  y_ad = st.text_input("Kitap Adı")
  y_yazar = st.text_input("Yazar")
  y_kat = st.text_input("Kategori")

  if st.button("Kaydet"):
    if y_ad and y_yazar:
      c.execute(
          "INSERT INTO kitaplar (ad, yazar, kategori) VALUES (?, ?, ?)",
          (y_ad, y_yazar, y_kat),
      )
      conn.commit()
      st.success(f"'{y_ad}' başarıyla eklendi!")
      st.rerun()
    else:
      st.warning("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")
        
