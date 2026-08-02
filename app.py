
import streamlit as st
import sqlite3
import qrcode
import io

st.set_page_config(page_title="Kişisel Kütüphanem", page_icon="📚", layout="centered")

def init_db():
    conn = sqlite3.connect("kutuphane.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kategoriler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT UNIQUE NOT NULL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kitaplar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        yazar TEXT,
        kategori_id INTEGER,
        okundu INTEGER DEFAULT 0,
        emanet_kisi TEXT DEFAULT '',
        FOREIGN KEY (kategori_id) REFERENCES kategoriler (id)
    )""")
    cursor.execute("INSERT OR IGNORE INTO kategoriler (ad) VALUES ('Roman'), ('Tarih'), ('Felsefe'), ('Bilim')")
    conn.commit()
    conn.close()

init_db()

st.title("📚 Kişisel Kütüphane Yönetimi")

# Kategori Ekleme
with st.expander("➕ Yeni Kategori Ekle"):
    yeni_kat = st.text_input("Kategori Adı")
    if st.button("Kategori Kaydet"):
        if yeni_kat:
            conn = sqlite3.connect("kutuphane.db")
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO kategoriler (ad) VALUES (?)", (yeni_kat,))
                conn.commit()
                st.success("Kategori eklendi!")
            except:
                st.warning("Bu kategori zaten var.")
            conn.close()

# Kitap Ekleme
st.subheader("Kitap Ekle")
conn = sqlite3.connect("kutuphane.db")
cursor = conn.cursor()
cursor.execute("SELECT id, ad FROM kategoriler")
kategoriler = cursor.fetchall()
kat_dict = {k[1]: k[0] for k in kategoriler}

col1, col2, col3 = st.columns([2, 2, 2])
with col1:
    k_ad = st.text_input("Kitap Adı")
with col2:
    k_yazar = st.text_input("Yazar")
with col3:
    k_kat = st.selectbox("Kategori", list(kat_dict.keys()) if kat_dict else ["Genel"])

if st.button("Kitabı Kaydet", type="primary"):
    if k_ad:
        kat_id = kat_dict.get(k_kat, 1)
        cursor.execute("INSERT INTO kitaplar (ad, yazar, kategori_id) VALUES (?, ?, ?)", (k_ad, k_yazar, kat_id))
        conn.commit()
        st.success("Kitap başarıyla eklendi!")
        st.rerun()

st.divider()

# Listeleme ve Filtreler
st.subheader("Kitap Listesi")
f_col1, f_col2 = st.columns(2)
with f_col1:
    secilen_kat = st.selectbox("Kategoriye Göre Filtrele", ["HEPSİ"] + list(kat_dict.keys()))
with f_col2:
    sadece_okunmayan = st.checkbox("Sadece Okunmayanlar")

query = "SELECT k.id, k.ad, k.yazar, kat.ad, k.okundu, k.emanet_kisi FROM kitaplar k LEFT JOIN kategoriler kat ON k.kategori_id = kat.id WHERE 1=1"
params = []
if secilen_kat != "HEPSİ":
    query += " AND k.kategori_id = ?"
    params.append(kat_dict[secilen_kat])
if sadece_okunmayan:
    query += " AND k.okundu = 0"

cursor.execute(query, params)
kitaplar = cursor.fetchall()
conn.close()

for k in kitaplar:
    k_id, k_ad, k_yazar, kat_ad, okundu, emanet = k
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"**{k_ad}** - *{k_yazar}* ({kat_ad})")
            if emanet:
                st.caption(f"🤝 Emanet Verilen Kişi: **{emanet}**")
        with c2:
            is_read = st.checkbox("Okundu", value=bool(okundu), key=f"read_{k_id}")
            if is_read != bool(okundu):
                conn = sqlite3.connect("kutuphane.db")
                conn.cursor().execute("UPDATE kitaplar SET okundu = ? WHERE id = ?", (1 if is_read else 0, k_id))
                conn.commit()
                conn.close()
                st.rerun()
        with c3:
            if st.button("QR / Emanet", key=f"qr_{k_id}"):
                st.session_state[f"show_qr_{k_id}"] = not st.session_state.get(f"show_qr_{k_id}", False)
        
        if st.session_state.get(f"show_qr_{k_id}", False):
            st.divider()
            q_col1, q_col2 = st.columns([1, 2])
            with q_col1:
                qr = qrcode.QRCode(version=1, box_size=4, border=1)
                qr.add_data(f"KITAP_ID:{k_id}")
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), width=150)
            with q_col2:
                yeni_emanet = st.text_input("Emanet Alacak Kişi", value=emanet, key=f"em_{k_id}")
                if st.button("Emanet Kaydet", key=f"save_em_{k_id}"):
                    conn = sqlite3.connect("kutuphane.db")
                    conn.cursor().execute("UPDATE kitaplar SET emanet_kisi = ? WHERE id = ?", (yeni_emanet, k_id))
                    conn.commit()
                    conn.close()
                    st.success("Emanet güncellendi!")
                    st.rerun()
