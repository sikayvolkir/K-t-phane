import io
import urllib.parse
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

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

# --- SUPABASE BAĞLANTISI ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- BAŞLIK VE ÖZETLER ---
st.title("📚 Kütüphane Yönetim Sistemi")

try:
    res_toplam = supabase.table("kitaplar").select("id", count="exact").execute()
    toplam_kitap = res_toplam.count if res_toplam.count is not None else 0
    
    res_emanet = supabase.table("kitaplar").select("id", count="exact").eq("durum", "Emanette").execute()
    emanette_kitap = res_emanet.count if res_emanet.count is not None else 0
except Exception:
    toplam_kitap = 0
    emanette_kitap = 0

m_col1, m_col2 = st.columns(2)
m_col1.metric(label="📖 Toplam Kitap Sayısı", value=toplam_kitap)
m_col2.metric(label="🔴 Emanetteki Kitap Sayısı", value=emanette_kitap)

st.divider()

# --- SESSION STATE VE BİLDİRİM YÖNETİMİ ---
if "form_key" not in st.session_state: st.session_state["form_key"] = 0
if "emanet_key" not in st.session_state: st.session_state["emanet_key"] = 0
if "kamera_acik" not in st.session_state: st.session_state["kamera_acik"] = False
if "selected_kitap_id" not in st.session_state: st.session_state["selected_kitap_id"] = None
if "bildirim" not in st.session_state: st.session_state["bildirim"] = None

if st.session_state["bildirim"]:
    b_tip, b_mesaj = st.session_state["bildirim"]
    if b_tip == "success":
        st.success(b_mesaj)
        st.toast(b_mesaj, icon="✅")
    elif b_tip == "error":
        st.error(b_mesaj)
        st.toast(b_mesaj, icon="⚠️")
    st.session_state["bildirim"] = None

def emanet_sifirla():
    st.session_state["kamera_acik"] = False
    st.session_state["selected_kitap_id"] = None
    st.session_state["emanet_key"] += 1

tab_ekle, tab_liste, tab_emanet = st.tabs(["➕ Yeni Kitap Ekle", "📖 Kitap Listesi & Filtreler", "📲 Emanet İşlemleri"])

# --- 1. SEKME: YENİ KİTAP EKLE ---
with tab_ekle:
    st.subheader("Sisteme Yeni Kitap Ekle")
    
    res_kat = supabase.table("kategoriler").select("ad").order("ad").execute()
    kategori_listesi = [row["ad"] for row in res_kat.data] if res_kat.data else []
    
    res_yazar = supabase.table("kitaplar").select("yazar").neq("yazar", "").execute()
    mevcut_yazarlar = sorted(list(set([row["yazar"] for row in res_yazar.data if row.get("yazar")]))) if res_yazar.data else []

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
            check_res = supabase.table("kitaplar").select("id").ilike("ad", kaydedilecek_ad).ilike("yazar", kaydedilecek_yazar).execute()
            if check_res.data:
                st.error(f"⚠️ '{kaydedilecek_ad}' isimli kitap zaten kayıtlı!")
            else:
                supabase.table("kitaplar").insert({
                    "ad": kaydedilecek_ad,
                    "yazar": kaydedilecek_yazar,
                    "kategori": y_kat,
                    "durum": "Kütüphanede",
                    "emanet_alan": "",
                    "okundu_durum": "Okunmadı"
                }).execute()
                st.session_state["form_key"] += 1
                st.session_state["bildirim"] = ("success", f"📚 '{kaydedilecek_ad}' kütüphaneye başarıyla eklendi!")
                st.rerun()
        else:
            st.warning("Lütfen Kitap Adı ve Yazar alanlarını doldurun.")

# --- 2. SEKME: KİTAP LİSTESİ ---
with tab_liste:
    st.subheader("📖 Kitap Envanteri")
    excel_col1, excel_col2 = st.columns(2)

    try:
        res_exp = supabase.table("kitaplar").select("kategori, ad, yazar, durum, emanet_alan, okundu_durum").order("id", desc=True).execute()
        tum_kitaplar_raw = res_exp.data
    except Exception:
        tum_kitaplar_raw = []

    if tum_kitaplar_raw:
        df_export = pd.DataFrame(tum_kitaplar_raw)
        df_export = df_export.rename(columns={
            "kategori": "Kategori", "ad": "Isim", "yazar": "Yazar",
            "durum": "Durum", "emanet_alan": "Emanet Alan", "okundu_durum": "Okunma Durumu"
        })
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

                            res_m = supabase.table("kitaplar").select("ad, yazar").execute()
                            mevcut_set = set([(r["ad"].lower(), r["yazar"].lower()) for r in res_m.data]) if res_m.data else set()
                            
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
                                        ekler.append({
                                            "ad": ad, "yazar": yazar, "kategori": kategori,
                                            "durum": "Kütüphanede", "emanet_alan": "", "okundu_durum": "Okunmadı"
                                        })
                                        kategoriler_to_add.add(kategori)
                                        mevcut_set.add((ad.lower(), yazar.lower()))

                            if kategoriler_to_add:
                                res_k = supabase.table("kategoriler").select("ad").execute()
                                mevc_kats = set([r["ad"] for r in res_k.data]) if res_k.data else set()
                                yeni_kats = [{"ad": k} for k in kategoriler_to_add if k not in mevc_kats]
                                if yeni_kats:
                                    supabase.table("kategoriler").insert(yeni_kats).execute()

                            if ekler:
                                supabase.table("kitaplar").insert(ekler).execute()

                            st.session_state["bildirim"] = ("success", f"🎉 {len(ekler)} kitap aktarıldı, {atlanan} mükerrer atlandı.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")

    with st.expander("🔍 Detaylı Filtreleme ve Arama", expanded=False):
        col1, col2 = st.columns(2)
        with col1: arama_metin = st.text_input("Kitap / Yazar Ara")
        with col2:
            res_tur = supabase.table("kategoriler").select("ad").order("ad").execute()
            turler_filtre = ["Tümü"] + ([row["ad"] for row in res_tur.data] if res_tur.data else [])
            f_tur = st.selectbox("Tür Filtresi", turler_filtre)
        col3, col4 = st.columns(2)
        with col3:
            res_yaz = supabase.table("kitaplar").select("yazar").neq("yazar", "").execute()
            yazarlar_filtre = ["Tümü"] + sorted(list(set([row["yazar"] for row in res_yaz.data]))) if res_yaz.data else ["Tümü"]
            f_yazar = st.selectbox("Yazar Filtresi", yazarlar_filtre)
        with col4: f_okundu = st.selectbox("Okunma Durumu", ["Tümü", "Okundu", "Okunmadı"])

    # Supabase Filtreli Sorgu
    query = supabase.table("kitaplar").select("id, ad, yazar, kategori, durum, emanet_alan, okundu_durum")
    if f_tur != "Tümü": query = query.eq("kategori", f_tur)
    if f_yazar != "Tümü": query = query.eq("yazar", f_yazar)
    if f_okundu != "Tümü": query = query.eq("okundu_durum", f_okundu)

    res_k = query.order("id", desc=True).execute()
    kitaplar = res_k.data if res_k.data else []

    if arama_metin:
        a_met = arama_metin.lower()
        kitaplar = [k for k in kitaplar if a_met in k["ad"].lower() or a_met in k["yazar"].lower()]

    st.divider()

    if kitaplar:
        for k in kitaplar:
            k_id, k_ad, k_yazar, k_kat, k_durum, k_emanet, k_okundu = k["id"], k["ad"], k["yazar"], k["kategori"], k["durum"], k["emanet_alan"], k["okundu_durum"]
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
                        supabase.table("kitaplar").update({"okundu_durum": yeni_durum}).eq("id", k_id).execute()
                        st.session_state["bildirim"] = ("success", f"#{k_id} ID'li kitabın durumu güncellendi.")
                        st.rerun()

                    if st.button("🗑️ Kitabı Sil", key=f"btn_sil_{k_id}", use_container_width=True):
                        supabase.table("kitaplar").delete().eq("id", k_id).execute()
                        st.session_state["bildirim"] = ("success", f"🗑️ '{k_ad}' kütüphaneden silindi.")
                        st.rerun()

                with col_qr:
                    qr_data = f"KITAP_ID:{k_id}"
                    encoded_qr_data = urllib.parse.quote(qr_data)
                    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_qr_data}"
                    st.image(qr_url, caption=f"ID: #{k_id}", width=150)
    else:
        st.info("Kriterlere uygun kitap bulunamadı.")

# --- 3. SEKME: EMANET İŞLEMLERİ ---
with tab_emanet:
    st.subheader("📲 Emanet / Teslim İşlemleri")

    res_emanette = supabase.table("kitaplar").select("id, ad, yazar, kategori, emanet_alan").eq("durum", "Emanette").order("id", desc=True).execute()
    emanetteki_kitaplar = res_emanette.data if res_emanette.data else []

    with st.expander(f"🔴 Emanetteki Kitaplar ({len(emanetteki_kitaplar)})", expanded=False):
        if emanetteki_kitaplar:
            for ek in emanetteki_kitaplar:
                ek_id, ek_ad, ek_yazar, ek_kat, ek_alan = ek["id"], ek["ad"], ek["yazar"], ek["kategori"], ek["emanet_alan"]
                with st.expander(f"📖 {ek_ad} (Kişi: {ek_alan})"):
                    st.write(f"**ID:** #{ek_id}")
                    st.write(f"**Yazar:** {ek_yazar}")
                    st.write(f"**Tür:** {ek_kat}")
                    st.write(f"**Emanet Alan Kişi:** {ek_alan}")
                    if st.button("📥 Kütüphaneye Geri Al", key=f"btn_list_geri_al_{ek_id}", use_container_width=True):
                        supabase.table("kitaplar").update({"durum": "Kütüphanede", "emanet_alan": ""}).eq("id", ek_id).execute()
                        st.session_state["bildirim"] = ("success", f"✅ '{ek_ad}' kütüphaneye geri alındı!")
                        emanet_sifirla()
                        st.rerun()
        else:
            st.info("Şu an emanette hiçbir kitap bulunmuyor.")

    st.markdown("---")
    ek_key = st.session_state["emanet_key"]

    islem_tipi = st.radio("Yapmak İstediğiniz İşlem:", ["Emanet Ver", "Emanetten Geri Al"], horizontal=True, key=f"radio_islem_{ek_key}")

    if islem_tipi == "Emanet Ver":
        res_u = supabase.table("kitaplar").select("id, ad, yazar").eq("durum", "Kütüphanede").order("ad").execute()
    else:
        res_u = supabase.table("kitaplar").select("id, ad, emanet_alan").eq("durum", "Emanette").order("ad").execute()

    uygun_kitaplar = res_u.data if res_u.data else []

    options_dict = {}
    default_index = 0

    if uygun_kitaplar:
        if islem_tipi == "Emanet Ver":
            options_dict = {f"#{k['id']} - {k['ad']} ({k['yazar']})": k['id'] for k in uygun_kitaplar}
        else:
            options_dict = {f"#{k['id']} - {k['ad']} (Emanette: {k['emanet_alan']})": k['id'] for k in uygun_kitaplar}

        if st.session_state["selected_kitap_id"] is not None:
            for idx, k_id_val in enumerate(options_dict.values()):
                if k_id_val == st.session_state["selected_kitap_id"]:
                    default_index = idx
                    break

        secilen_label = st.selectbox("Listeden Kitap Seçin:", list(options_dict.keys()), index=default_index, key=f"select_kitap_{ek_key}")
        if secilen_label:
            st.session_state["selected_kitap_id"] = options_dict[secilen_label]
    else:
        st.session_state["selected_kitap_id"] = None
        if islem_tipi == "Emanet Ver":
            st.info("Emanet verilebilecek uygun kitap bulunmuyor.")
        else:
            st.info("Şu an emanette kitap bulunmuyor.")

    with st.expander("Manuel Kitap ID Gir"):
        manual_id_input = st.number_input("Kitap ID:", min_value=1, step=1, key=f"manual_id_{ek_key}")
        if st.button("Bu ID'yi Kullan", key=f"btn_manual_set_{ek_key}"):
            st.session_state["selected_kitap_id"] = int(manual_id_input)
            st.toast(f"🎯 ID #{manual_id_input} seçildi!")

    if not st.session_state["kamera_acik"]:
        if st.button("📷 Canlı QR Kamerasını Aç", use_container_width=True, key=f"btn_cam_open_{ek_key}"):
            st.session_state["kamera_acik"] = True
            st.rerun()
    else:
        if st.button("❌ Kamerayı Kapat", use_container_width=True, key=f"btn_cam_close_{ek_key}"):
            st.session_state["kamera_acik"] = False
            st.rerun()

        st.caption("📷 Arka kamera ile QR kod taranıyor...")

        scanner_html = r"""
        <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
        <div style="width:100%; max-width:400px; margin:auto; text-align:center;">
          <video id="v" style="width:100%; border-radius:10px; background:#000;" autoplay playsinline muted></video>
          <canvas id="c" style="display:none;"></canvas>
          <div id="st" style="margin-top:6px; font-weight:bold; color:#4A5335;">Kamera Açılıyor...</div>
        </div>
        <script>
        const video = document.getElementById("v");
        const canvas = document.getElementById("c");
        const ctx = canvas.getContext("2d");
        const stDiv = document.getElementById("st");
        let active = true;

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
        .then(function(stream) {
          video.srcObject = stream;
          video.setAttribute("playsinline", true);
          video.play();
          stDiv.innerText = "QR Kodu Hizalayın...";
          requestAnimationFrame(scan);
        })
        .catch(function(err) {
          stDiv.innerText = "Kamera Başlatılamadı!";
        });

        function scan() {
          if (!active) return;
          if (video.readySta
