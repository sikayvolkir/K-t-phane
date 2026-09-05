import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ---------------------------------------------------------
# 1. SUPABASE BAĞLANTISI
# ---------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ---------------------------------------------------------
# 2. SAYFA VE SESSION STATE AYARLARI
# ---------------------------------------------------------
st.set_page_config(page_title="Kütüphane Takip Sistemi", page_icon="📚", layout="wide")

if "kamera_acik" not in st.session_state:
    st.session_state["kamera_acik"] = False
if "selected_kitap_id" not in st.session_state:
    st.session_state["selected_kitap_id"] = None

# QR Kod Dinleyicisi (URL Query Params)
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
# 3. SEKME YAPISI
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📖 Kitap Listesi", "➕ Yeni Kitap Ekle", "🔄 Emanet / İade İşlemleri"])

# --- TAB 1: KİTAP LİSTESİ ---
with tab1:
    st.subheader("Kütüphanedeki Tüm Kitaplar")
    try:
        response = supabase.table("kitaplar").select("*").execute()
        data = response.data

        if data:
            df = pd.DataFrame(data)
            # Kolon isimlerini düzenleme (Tablo sütun adlarınıize göre esnek)
            rename_dict = {
                "id": "ID",
                "baslik": "Kitap Adı",
                "kitap_adi": "Kitap Adı",
                "yazar": "Yazar",
                "yazar_adi": "Yazar",
                "isbn": "ISBN",
                "durum": "Durum",
                "odunc_alan": "Ödünç Alan"
            }
            df = df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns})
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Kütüphanede henüz kayıtlı kitap bulunmamaktadır.")
    except Exception as e:
        st.error(f"Supabase veri çekme hatası: {e}")

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
                try:
                    payload = {
                        "baslik": baslik.strip(),
                        "yazar": yazar.strip(),
                        "isbn": isbn.strip(),
                        "durum": "Kütüphanede"
                    }
                    supabase.table("kitaplar").insert(payload).execute()
                    st.success(f"'{baslik}' kitabı Supabase veritabanına başarıyla eklendi!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Kayıt eklenirken hata oluştu: {e}")
            else:
                st.error("Lütfen kitap adı ve yazar alanlarını doldurun.")

# --- TAB 3: EMANET / İADE VE QR TARAMA ---
with tab3:
    st.subheader("Kitap Ödünç / İade İşlemleri")

    try:
        res = supabase.table("kitaplar").select("*").execute()
        kitaplar_listesi = res.data
    except Exception as e:
        kitaplar_listesi = []
        st.error(f"Veri okunamadı: {e}")

    options = []
    id_map = {}
    for row in kitaplar_listesi:
        kitap_adi = row.get("baslik") or row.get("kitap_adi", "Bilinmeyen Kitap")
        label = f"#{row['id']} - {kitap_adi} ({row.get('durum', '-')})"
        options.append(label)
        id_map[row['id']] = row

    selected_index = 0
    if st.session_state["selected_kitap_id"] is not None:
        target_id = st.session_state["selected_kitap_id"]
        for idx, row in enumerate(kitaplar_listesi):
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

    # GELİŞMİŞ QR TARAYICI (KAMERA)
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
            video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } } 
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
              const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "dontInvert" });

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
                  if (streamRef) streamRef.getTracks().forEach(track => track.stop());
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

    # İŞLEM FORMU
    if kitaplar_listesi and seçilen_label != "Kayıtlı Kitap Yok":
        selected_id = int(seçilen_label.split(" - ")[0].replace("#", ""))
        secili_kitap = id_map.get(selected_id)

        if secili_kitap:
            st.divider()
            kitap_baslik = secili_kitap.get("baslik") or secili_kitap.get("kitap_adi", "")
            kitap_yazar = secili_kitap.get("yazar") or secili_kitap.get("yazar_adi", "")
            st.write(f"**Seçili Kitap:** {kitap_baslik} - *{kitap_yazar}*")
            st.write(f"**Mevcut Durum:** `{secili_kitap.get('durum', 'Bilinmiyor')}`")

            if secili_kitap.get("durum") == "Ödünç Verildi":
                st.info(f"Bu kitap şu anda **{secili_kitap.get('odunc_alan', '-')}** isimli kişide.")
                if st.button("📥 Kitabı İade Al"):
                    supabase.table("kitaplar").update({"durum": "Kütüphanede", "odunc_alan": None}).eq("id", selected_id).execute()
                    st.success("Kitap başarıyla iade alındı!")
                    st.rerun()
            else:
                odunc_alan_kisi = st.text_input("Kitabı Ödünç Alan Kişinin Adı Soyadı")
                if st.button("📤 Ödünç Ver"):
                    if odunc_alan_kisi.strip():
                        supabase.table("kitaplar").update({"durum": "Ödünç Verildi", "odunc_alan": odunc_alan_kisi.strip()}).eq("id", selected_id).execute()
                        st.success(f"Kitap {odunc_alan_kisi} kişisine ödünç verildi!")
                        st.rerun()
                    else:
                        st.warning("Lütfen ödünç alan kişinin adını girin.")
                        
