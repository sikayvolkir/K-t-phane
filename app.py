import sqlite3
import streamlit as st

# Sayfa Yapılandırması
st.set_page_config(
    page_title="Kütüphane Yönetimi", page_icon="📚", layout="centered"
)

# --- VERİTABANI BAĞLANTISI ---
conn = sqlite3.connect("kutuphane.db", check_same_thread=False)
c = conn.cursor()

# Tabloları Güvenli Oluştur (Veri Kaybını Önler)
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

# Eksik Sütun Kontrolü (Silmeden Güvenli Güncelleme)
try:
  c.execute("SELECT okundu_durum FROM kitaplar LIMIT 1")
except sqlite3.OperationalError:
  c.execute(
      "ALTER TABLE kitaplar ADD COLUMN okundu_durum TEXT DEFAULT 'Okunmadı'"
  )

# Varsayılan Türleri Ekle (Eğer boşsa)
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

st.title("📚 Kütüphane Yönetim Sistemi")

# --- SEKMELER ---
tab_ekle, tab_liste, tab_emanet = st.tabs(
    ["➕ Yeni Kitap Ekle", "📖 Kitap Listesi & Filtreler", "📲 Emanet İşlemleri"]
)

# ==========================================
# 1. SEKME: YENİ KİTAP EKLE (ANA EKRAN)
# ==========================================
with tab_ekle:
  st.subheader("Sisteme Yeni Kitap Ekle")

  # Dinamik Türleri Çek
  c.execute("SELECT ad FROM kategoriler ORDER BY ad ASC")
  kategori_listesi = [row[0] for row in c.fetchall()]

  # Mevcut Yazarları Çek
  c.execute(
      "SELECT DISTINCT yazar FROM kitaplar WHERE yazar != '' ORDER BY yazar ASC"
  )
  mevcut_yazarlar = [row[0] for row in c.fetchall()]

  y_ad = st.text_input("Kitap Adı:")

  y_yazar_secim = st.selectbox(
      "Önceki Yazarlardan Seç (İsteğe Bağlı):",
      ["-- Yeni Yazar Girin --"] + mevcut_yazarlar,
  )
  if y_yazar_secim == "-- Yeni Yazar Girin --":
    y_yazar = st.text_input("Yazar Adı Soyadı:")
  else:
    y_yazar = st.text_input("Yazar Adı Soyadı:", value=y_yazar_secim)

  y_kat = st.selectbox("Kitap Türü (Kategori):", kategori_listesi)
  y_okundu = st.radio(
      "Okunma Durumu:", ["Okunmadı", "Okundu"], horizontal=True
  )

  if st.button("Kitabı Kaydet", use_container_width=True):
    if y_ad.strip() and y_yazar.strip():
      # Mükerrer Kayıt Kontrolü
      c.execute(
          "SELECT id FROM kitaplar WHERE LOWER(ad) = LOWER(?) AND LOWER(yazar)"
          " = LOWER(?)",
          (y_ad.strip(), y_yazar.strip()),
      )
      if c.fetchone():
        st.error(
            f"⚠️ **Uyarı:** '{y_ad}' isimli kitap **{y_yazar}** yazarı ile zaten"
            " kütüphanede kayıtlı!"
        )
      else:
        c.execute(
            """
                    INSERT INTO kitaplar (ad, yazar, kategori, okundu_durum) 
                    VALUES (?, ?, ?, ?)
                """,
            (y_ad.strip(), y_yazar.strip(), y_kat, y_okundu),
        )
        conn.commit()
        st.success(f"✅ '{y_ad}' başarıyla eklendi!")
        st.rerun()
    else:
      st.warning("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")

# ==========================================
# 2. SEKME: KİTAP LİSTESİ, FİLTRELER VE DURUM GÜNCELLEME
# ==========================================
with tab_liste:
  st.subheader("📖 Kitap Envanteri")

  # --- FİLTRELEME ALANI ---
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

  # Sorgu Oluşturma
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

  # Listeleme
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
          # Listeden Okundu / Okunmadı Seçimi
          yeni_okundu_secim = st.selectbox(
              "Okuma Durumu:",
              ["Okunmadı", "Okundu"],
              index=0 if k_okundu == "Okunmadı" else 1,
              key=f"sel_okundu_{k_id}",
          )
          if yeni_okundu_secim != k_okundu:
            c.execute(
                "UPDATE kitaplar SET okundu_durum = ? WHERE id = ?",
                (yeni_okundu_secim, k_id),
            )
            conn.commit()
            st.toast(f"#{k_id} '{k_ad}' durumu güncellendi!")
            st.rerun()
        st.divider()
  else:
    st.info("Kriterlere uygun kitap bulunamadı.")

  # --- KİTAP TÜRLERİ (KATEGORİ) YÖNETİM AYARI ---
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
          st.success(f"'{yeni_tur}' türü eklendi!")
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
        st.success(f"'{silinecek_tur}' türü silindi!")
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
          st.success(
              f"✅ '{ad}' kitabı başarıyla **{kisi_adi}** kişisine teslim"
              " edildi!"
          )
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
          st.success(f"✅ '{ad}' kitabı kütüphaneye geri teslim alındı!")
          st.rerun()
    else:
      st.error("Bu ID'ye sahip bir kitap bulunamadı.")
