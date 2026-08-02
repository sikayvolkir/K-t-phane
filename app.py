import sqlite3
import streamlit as st

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Kütüphane Yönetim Sistemi",
    page_icon="📚",
    layout="wide"
)

# --- VERİTABANI BAĞLANTISI VE OTOMATİK MİGRASYON ---
conn = sqlite3.connect("kutuphane.db", check_same_thread=False)
c = conn.cursor()

# 1. Tabloyu oluştur (yoksa)
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

# 2. Şema kontrolü ve eksik sütunları ekleme (Migrasyon)
c.execute("PRAGMA table_info(kitaplar)")
mevcut_sutunlar = [col[1] for col in c.fetchall()]

if "durum" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN durum TEXT DEFAULT 'Kütüphanede'")
if "emanet_alan" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN emanet_alan TEXT DEFAULT ''")
if "okundu_durum" not in mevcut_sutunlar:
    c.execute("ALTER TABLE kitaplar ADD COLUMN okundu_durum TEXT DEFAULT 'Okunmadı'")

conn.commit()


# --- YARDIMCI FONKSİYONLAR ---
def kitaplari_getir():
    c.execute("SELECT * FROM kitaplar")
    return c.fetchall()

def kitap_ekle(ad, yazar, kategori):
    c.execute(
        "INSERT INTO kitaplar (ad, yazar, kategori, durum, emanet_alan, okundu_durum) VALUES (?, ?, ?, 'Kütüphanede', '', 'Okunmadı')",
        (ad, yazar, kategori)
    )
    conn.commit()

def kitap_sil(kitap_id):
    c.execute("DELETE FROM kitaplar WHERE id = ?", (kitap_id,))
    conn.commit()

def emanet_ver(kitap_id, kisi_adi):
    c.execute(
        "UPDATE kitaplar SET durum = 'Emanette', emanet_alan = ? WHERE id = ?",
        (kisi_adi, kitap_id)
    )
    conn.commit()

def iade_al(kitap_id):
    c.execute(
        "UPDATE kitaplar SET durum = 'Kütüphanede', emanet_alan = '' WHERE id = ?",
        (kitap_id,)
    )
    conn.commit()

def okuma_durumu_guncelle(kitap_id, yeni_durum):
    c.execute(
        "UPDATE kitaplar SET okundu_durum = ? WHERE id = ?",
        (yeni_durum, kitap_id)
    )
    conn.commit()


# --- KULLANICI ARAYÜZÜ (STREAMLIT) ---
st.title("📚 Kütüphane Yönetim Sistemi")

# Metrik Özetleri
col1, col2, col3 = st.columns(3)

c.execute("SELECT COUNT(*) FROM kitaplar")
toplam_kitap = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM kitaplar WHERE durum = 'Emanette'")
emanetteki_kitap = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM kitaplar WHERE durum = 'Kütüphanede'")
kutuphanedeki_kitap = c.fetchone()[0]

col1.metric("Toplam Kitap", toplam_kitap)
col2.metric("Kütüphanede", kutuphanedeki_kitap)
col3.metric("Emanette", emanetteki_kitap)

st.markdown("---")

# Yan Menü - Navigasyon
sayfa = st.sidebar.radio(
    "Menü",
    ["Kitap Listesi & Arama", "Yeni Kitap Ekle", "Emanet & İade İşlemleri", "Kitap Sil"]
)

# --- 1. SİL / LİSTELE & ARAMA ---
if sayfa == "Kitap Listesi & Arama":
    st.subheader("📖 Kitap Listesi")
    
    arama_kelimesi = st.text_input("🔍 Kitap Adı veya Yazar Ara")
    
    if arama_kelimesi:
        c.execute(
            "SELECT * FROM kitaplar WHERE ad LIKE ? OR yazar LIKE ?",
            (f"%{arama_kelimesi}%", f"%{arama_kelimesi}%")
        )
        kitaplar = c.fetchall()
    else:
        kitaplar = kitaplari_getir()

    if kitaplar:
        for k in kitaplar:
            # k: (id, ad, yazar, kategori, durum, emanet_alan, okundu_durum)
            k_id, ad, yazar, kategori, durum, emanet_alan, okundu = k
            
            with st.expander(f"📌 {ad} - {yazar} ({durum})"):
                st.write(f"**Kategori:** {kategori}")
                st.write(f"**Emanet Durumu:** {durum}")
                if durum == "Emanette":
                    st.write(f"**Emanet Alan:** {emanet_alan}")
                
                # Okundu Durumu Seçimi
                yeni_okundu = st.selectbox(
                    "Okuma Durumu",
                    ["Okunmadı", "Okunuyor", "Okundu"],
                    index=["Okunmadı", "Okunuyor", "Okundu"].index(okundu if okundu else "Okunmadı"),
                    key=f"okundu_{k_id}"
                )
                if yeni_okundu != okundu:
                    okuma_durumu_guncelle(k_id, yeni_okundu)
                    st.success("Okuma durumu güncellendi!")
                    st.rerun()
    else:
        st.info("Kayıtlı kitap bulunamadı.")

# --- 2. YENİ KİTAP EKLE ---
elif sayfa == "Yeni Kitap Ekle":
    st.subheader("➕ Yeni Kitap Ekle")
    
    with st.form("kitap_ekle_formu", clear_on_submit=True):
        ad = st.text_input("Kitap Adı*")
        yazar = st.text_input("Yazar*")
        kategori = st.text_input("Kategori")
        
        submit = st.form_submit_button("Kaydet")
        
        if submit:
            if ad.strip() and yazar.strip():
                kitap_ekle(ad.strip(), yazar.strip(), kategori.strip())
                st.success(f"'{ad}' kütüphaneye eklendi!")
                st.rerun()
            else:
                st.error("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")

# --- 3. EMANET & İADE İŞLEMLERİ ---
elif sayfa == "Emanet & İade İşlemleri":
    st.subheader("🔄 Emanet & İade İşlemleri")
    
    tab1, tab2 = st.tabs(["Emanet Ver", "İade Al"])
    
    with tab1:
        c.execute("SELECT id, ad FROM kitaplar WHERE durum = 'Kütüphanede'")
        kutuphanedekiler = c.fetchall()
        
        if kutuphanedekiler:
            secilen_kitap = st.selectbox(
                "Emanet Verilecek Kitap",
                options=kutuphanedekiler,
                format_func=lambda x: x[1]
            )
            kisi = st.text_input("Emanet Edilecek Kişi")
            
            if st.button("Emanet Ver"):
                if kisi.strip():
                    emanet_ver(secilen_kitap[0], kisi.strip())
                    st.success("Kitap başarıyla emanet edildi!")
                    st.rerun()
                else:
                    st.warning("Lütfen kişi adını girin.")
        else:
            st.info("Emanet verilebilecek uygun kitap yok.")
            
    with tab2:
        c.execute("SELECT id, ad, emanet_alan FROM kitaplar WHERE durum = 'Emanette'")
        emanetteki_list = c.fetchall()
        
        if emanetteki_list:
            secilen_iade = st.selectbox(
                "İade Alınacak Kitap",
                options=emanetteki_list,
                format_func=lambda x: f"{x[1]} (Emanette: {x[2]})"
            )
            
            if st.button("İade Al"):
                iade_al(secilen_iade[0])
                st.success("Kitap başarıyla iade alındı!")
                st.rerun()
        else:
            st.info("Emanette kitap bulunmuyor.")

# --- 4. KİTAP SİL ---
elif sayfa == "Kitap Sil":
    st.subheader("🗑️ Kitap Sil")
    
    tum_kitaplar = kitaplari_getir()
    if tum_kitaplar:
        silinecek = st.selectbox(
            "Silinecek Kitabı Seçin",
            options=tum_kitaplar,
            format_func=lambda x: f"{x[1]} - {x[2]}"
        )
        
        if st.button("Kitabı Sil", type="primary"):
            kitap_sil(silinecek[0])
            st.success("Kitap silindi.")
            st.rerun()
    else:
        st.info("Silinecek kitap yok.")
