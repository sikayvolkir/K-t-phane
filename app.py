import streamlit as st
import sqlite3
import pandas as pd

# ---------------------------------------------------------
# 1. VERİTABANI BAĞLANTISI VE TABLO OLUŞTURMA
# ---------------------------------------------------------
DB_FILE = "kutuphane.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_sqlite_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS kitaplar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                baslik TEXT NOT NULL,
                yazar TEXT NOT NULL,
                isbn TEXT,
                durum TEXT DEFAULT 'Kütüphanede',
                odunc_alan TEXT
            )
        """)
        conn.commit()

init_sqlite_db()

# ---------------------------------------------------------
# 2. SAYFA AYARLARI VE SESSION STATE İLK DEĞERLERİ
# ---------------------------------------------------------
st.set_page_config(page_title="Kütüphane Takip Sistemi", page_icon="📚", layout="wide")

if "kamera_acik" not in st.session_state:
    st.session_state["kamera_acik"] = False
if "selected_kitap_id" not in st.session_state:
    st.session_state["selected_kitap_id"] = None

# ---------------------------------------------------------
# 3. QR KOD TARAYICI DİNLEYİCİSİ (QUERY PARAMS YAKALAMA)
# ---------------------------------------------------------
if "qr_scanned_id" in st.query_params:
    try:
        scanned_id = int(st.query_params["qr_scanned_id"])
        st.session_state["selected_kitap_id"] = scanned_id
        st.session_state["kamera_acik"] = False
        st.toast(f"🎯 QR Kod Okundu! Seçilen Kitap ID: #{scanned_id}", icon="✅")
    except ValueError:
        pass
    st.query_params.clear()

st.title("📚 Kütüphane Otomasyon Sistemi")

# ---------------------------------------------------------
# 4. SEKME YAPISI (TABS)
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📖 Kitap Listesi", "➕ Yeni Kitap Ekle", "🔄 Emanet / İade İşlemleri"])

# --- TAB 1: KİTAP LİSTESİ ---
with tab1:
    st.subheader("Kütüphanedeki Tüm Kitaplar")
    
    conn = get_connection()
    try:
        # Tırnak işaretleri SQLite standartlarına uygun çift tırnak (") ile güncellendi
        query = 'SELECT id AS "ID", baslik AS "Kitap Adı", yazar AS "Yazar", isbn AS "ISBN", durum AS "Durum", odunc_alan AS "Ödünç Alan" FROM kitaplar'
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        df = pd.DataFrame()
        st.error(f"Veri okunurken hata oluştu: {e}")
    finally:
        conn.close()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Kütüphanede henüz kayıtlı kitap bulunmamaktadır.")

# --- TAB 2: YENİ KİTAP EKLE ---
with tab2:
    st.subheader("Yeni Kitap Kaydı")
    with st.form(key="yeni_kitap_formu", clear_on_submit=True):
        baslik = st.text_input("Kitap Adı *")
        yazar = st.text_input("Yazar *")
        isbn = st.text_input("ISBN / Barkod Numarası")
        
        submit_button = st.form_submit_button(label="Kitabı Kaydet")
        
        if submit_button:
            if baslik.strip() and yazar.strip():
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO kitaplar (baslik, yazar, isbn) VALUES (?, ?, ?)",
                        (baslik.strip(), yazar.strip(), isbn.strip())
                    )
                    conn.commit()
                st.success(f"'{baslik}' kitabı başarıyla kütüphaneye eklendi!")
                st.rerun()
            else:
                st.error("Lütfen kitap adı ve yazar alanlarını doldurun.")

# --- TAB 3: EMANET / İADE VE QR TARAMA ---
with tab3:
    st.subheader("Kitap Ödünç / İade İşlemleri")

    conn = get_connection()
    kitaplar_listesi = pd.read_sql_query("SELECT id, baslik, durum FROM kitaplar", conn)
    conn.close()

    options = []
    for _, row in kitaplar_listesi.iterrows():
        label = f"#{row['id']} - {row['baslik']} ({row['durum']})"
        options.append(label)

    selected_index = 0
    if st.session_state["selected_kitap_id"] is not None:
        target_id = st.session_state["selected_kitap_id"]
        for idx, row in kitaplar_listesi.iterrows():
            if row['id'] == target_id:
                selected_index = idx
                break

    c1, c2 = st.columns([3, 1])
    with c1:
        seçilen_label = st.selectbox(
            "İşlem Yapılacak Kitabı Seçin",
            options=options if options else ["Kayıtlı Kitap Yok"],
            index=selected_index if options and selected_index < len(options) else 0
        )
    with c2:
        st.write("")
        st.write("")
        if st.button("📷 QR / Kamera Aç", use_container_width=True):
            st.session_state["kamera_acik"] = not st.session_state["kamera_acik"]

    # GELİŞMİŞ QR TARAYICI (KAMERA) BÖLÜMÜ
    if st.session_state["kamera_acik"]:
        st.info("Kameranızı QR koda doğru tutun.")
        
        scanner_html = r"""
        <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
        <div style="width:100%; max-width:420px; margin:0 auto; text-align:center; font-family:sans-serif;">
          <div style="position:relative; width:100%; border-radius:12px; overflow:hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <video id="qr-video" style="width:100%; height:auto; display:block; background:#000;" autoplay playsinline muted></video>
            <div id="qr-overlay" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; display:flex; align-items:center; justify-content:center;">
              <div style="width:200px; height:200px; border:2px dashed #4A5335; border-radius:12px; box-shadow:0 0 0 4000px rgba(0,0,0,0.3);"></div>
            </div>
          </div>
          <canvas id="qr-canvas" style="display:none;"></canvas>
          <div id="qr-status" style="margin-top:10px; font-size:14px; font-weight:600; color:#4A5335; background:#EAE5D9; padding:8px 12px; border-radius:6px;">
            📷 Kamera erişimi bekleniyor...
          </div>
        </div>

        <script>
        (function() {
          const video = document.getElementById("qr-video");
          const canvas = document.getElementById("qr-canvas");
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
          const statusDiv = document.getElementById("qr-status");
          
          let isScanning = true;
          let streamRef = null;

          navigator.mediaDevices.getUserMedia({ 
            video: { 
              facingMode: { ideal: "environment" },
              width: { ideal: 1280 },
              height: { ideal: 720 }
            } 
          })
          .then(function(stream) {
            streamRef = stream;
            video.srcObject = stream;
            video.setAttribute("playsinline", true);
            video.play();
            statusDiv.innerText = "🎯 QR Kodu Çerçeveye Hizalayın";
            requestAnimationFrame(tick);
          })
          .catch(function(err) {
            statusDiv.innerText = "❌ Kamera Başlatılamadı: " + err.message;
            statusDiv.style.color = "#a94442";
          });

          function tick() {
            if (!isScanning) return;

            if (video.readyState === video.HAVE_ENOUGH_DATA) {
              canvas.height = video.videoHeight;
              canvas.width = video.videoWidth;
              ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
              
              const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
              const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
              });

              if (code && code.data) {
                const scannedData = code.data.trim();
                
                let targetId = null;
                if (scannedData.startsWith("KITAP_ID:")) {
                  targetId = scannedData.replace("KITAP_ID:", "").trim();
                } else if (!isNaN(scannedData)) {
                  targetId = scannedData;
                }

                if (targetId) {
                  isScanning = false;
                  statusDiv.innerText = "✅ Okundu! Kitap ID: #" + targetId;
                  statusDiv.style.color = "#2e6da4";

                  if (streamRef) {
                    streamRef.getTracks().forEach(track => track.stop());
                  }

                  setTimeout(() => {
                    const currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set("qr_scanned_id", targetId);
                    window.location.href = currentUrl.toString();
                  }, 400);
                  return;
                }
              }
            }
            requestAnimationFrame(tick);
          }
        })();
        </script>
        """
        st.components.v1.html(scanner_html, height=360)

    # İŞLEM FORMU (ÖDÜNÇ / İADE)
    if not kitaplar_listesi.empty and seçilen_label != "Kayıtlı Kitap Yok":
        selected_id = int(seçilen_label.split(" - ")[0].replace("#", ""))
        
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT baslik, yazar, durum, odunc_alan FROM kitaplar WHERE id = ?", (selected_id,))
            secili_kitap = c.fetchone()

        if secili_kitap:
            st.divider()
            st.write(f"**Seçili Kitap:** {secili_kitap[0]} - *{secili_kitap[1]}*")
            st.write(f"**Mevcut Durum:** `{secili_kitap[2]}`")

            if secili_kitap[2] == "Ödünç Verildi":
                st.info(f"Bu kitap şu anda **{secili_kitap[3]}** isimli kişide.")
                if st.button("📥 Kitabı İade Al"):
                    with get_connection() as conn:
                        c = conn.cursor()
                        c.execute("UPDATE kitaplar SET durum = 'Kütüphanede', odunc_alan = NULL WHERE id = ?", (selected_id,))
                        conn.commit()
                    st.success("Kitap başarıyla iade alındı!")
                    st.rerun()
            else:
                odunc_alan_kisi = st.text_input("Kitabı Ödünç Alan Kişinin Adı Soyadı")
                if st.button("📤 Ödünç Ver"):
                    if odunc_alan_kisi.strip():
                        with get_connection() as conn:
                            c = conn.cursor()
                            c.execute("UPDATE kitaplar SET durum = 'Ödünç Verildi', odunc_alan = ? WHERE id = ?", (odunc_alan_kisi.strip(), selected_id))
                            conn.commit()
                        st.success(f"Kitap {odunc_alan_kisi} kişisine ödünç verildi!")
                        st.rerun()
                    else:
                        st.warning("Lütfen ödünç alan kişinin adını girin.")
                        
