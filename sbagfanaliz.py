import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="AGF Takip Paneli", layout="centered")
st.title("🐎 AGF Takip ve Analiz Web Paneli")

st.markdown("### TJK AGF Sayfası Linki")
agf_url = st.text_input("TJK AGF Sayfası Linki", "https://www.tjk.org/TR/YarisSever/Query/Page/AkisyonSonuclari")

saat_input = st.text_input("Veri çekim saatlerini girin (örn: 14:00,15:15,16:30)", "14:00,15:30")
cek_buton = st.button("🔍 Verileri Çek ve Analiz Et")

progress_bar = st.empty()
status_text = st.empty()
sonuc_alan = st.empty()

agf_data_dict = {}
sunucu_farki = 3  # Türkiye ile UTC farkı
output_file = "agf_zaman_serisi_ve_analiz.xlsx"

# --- Yardımcı Fonksiyonlar ---
def belirle_surpriz_tipi(row, saatler):
    try:
        agf_values = row[1:-1].dropna().astype(float)
        if len(agf_values) < 3:
            return ""

        ilk_agf = agf_values.iloc[0]
        son_agf = agf_values.iloc[-1]
        fark_ilk_son = son_agf - ilk_agf

        if son_agf < 10 and fark_ilk_son >= 1.0:
            return f"SÜRPRİZ (%+{fark_ilk_son:.1f})"

        if len(saatler) >= 2:
            son1 = row[saatler[-1]]
            son2 = row[saatler[-2]]
            if pd.notna(son1) and pd.notna(son2):
                fark_son_dk = float(son1) - float(son2)
                if fark_son_dk >= 0.3 and float(son1) < 10:
                    return f"Son DK Sürpriz (%+{fark_son_dk:.1f})"
    except:
        return ""
    return ""

def fetch_agf():
    now = datetime.utcnow() + timedelta(hours=sunucu_farki)
    timestamp = now.strftime("%H:%M")
    status_text.info(f"⏳ [{timestamp}] AGF verisi çekiliyor...")

    try:
        response = requests.get(agf_url)
        soup = BeautifulSoup(response.content, "html.parser")

        for ayak in range(1, 7):
            table = soup.find("table", {"id": f"GridView{ayak}"})
            if not table:
                continue
            rows = table.find_all("tr")[1:]
            current_data = []
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    cell_text = cells[1].text.strip()
                    if "(" in cell_text and "%" in cell_text:
                        at_no = cell_text.split("(")[0].strip()
                        agf_percent = cell_text.split("%")[-1].replace(")", "").replace(",", ".")
                        current_data.append((at_no, float(agf_percent)))

            df = pd.DataFrame(current_data, columns=["At", timestamp])
            if ayak not in agf_data_dict or agf_data_dict[ayak].empty:
                agf_data_dict[ayak] = df
            else:
                agf_data_dict[ayak] = pd.merge(agf_data_dict[ayak], df, on="At", how="outer")

        status_text.success(f"✅ [{timestamp}] Veri çekildi.")
    except Exception as e:
        status_text.error(f"⚠️ Hata: {e}")

def analiz_ve_goster():
    for ayak, df in agf_data_dict.items():
        df = df.dropna(how="all", axis=1)
        if df.shape[1] < 3:
            st.warning(f"{ayak}. ayakta yeterli veri yok.")
            continue

        saatler = df.columns[1:].tolist()
        last_col = df.columns[-1]
        prev_col = df.columns[-2]

        df["Toplam AGF Değişim %"] = df[last_col] - df[df.columns[1]]
        df["Sabit Çok Değişmeyen AGFLER"] = df[df.columns[1:-1]].std(axis=1)
        df["Sürekli Artış Göstermiş Atlar"] = df[df.columns[1:-1]].diff(axis=1).apply(lambda x: sum([1 if v > 0 else -1 if v < 0 else 0 for v in x.dropna()]), axis=1)
        df["Sürpriz Tipi"] = df.apply(lambda row: belirle_surpriz_tipi(row, saatler), axis=1)

        max_values = {
            "Sürekli Artış Göstermiş Atlar": df["Sürekli Artış Göstermiş Atlar"].max(),
            "Toplam AGF Değişim %": df["Toplam AGF Değişim %"].max(),
            "Sabit Çok Değişmeyen AGFLER": df["Sabit Çok Değişmeyen AGFLER"].max()
        }

        def highlight(val, col):
            try:
                if pd.isna(val): return ""
                if val == max_values[col]:
                    return "background-color: lightgreen"
                if col == "Toplam AGF Değişim %" and val >= 0.74:
                    return "background-color: orange"
                if col in ["Sürekli Artış Göstermiş Atlar", "Sabit Çok Değişmeyen AGFLER"]:
                    top3 = df[col].sort_values(ascending=False).drop_duplicates().nlargest(4)[1:]
                    if val in top3.values:
                        return "background-color: orange"
            except:
                return ""
            return ""

        styled_df = df.style.applymap(lambda v: highlight(v, "Sürekli Artış Göstermiş Atlar"), subset=["Sürekli Artış Göstermiş Atlar"])\
                          .applymap(lambda v: highlight(v, "Toplam AGF Değişim %"), subset=["Toplam AGF Değişim %"])\
                          .applymap(lambda v: highlight(v, "Sabit Çok Değişmeyen AGFLER"), subset=["Sabit Çok Değişmeyen AGFLER"])

        st.subheader(f"📊 {ayak}. Ayak Analizi")
        try:
            st.dataframe(styled_df, use_container_width=True)
        except:
            st.write(df)

if cek_buton:
    saatler = [s.strip() for s in saat_input.split(",") if s.strip()]
    toplam = len(saatler)
    for i, hedef_saat in enumerate(saatler):
        while True:
            simdi = datetime.utcnow() + timedelta(hours=sunucu_farki)
            if simdi.strftime("%H:%M") == hedef_saat:
                fetch_agf()
                break
            progress_bar.progress(int(i / toplam * 100))
            status_text.info(f"⏳ Lütfen bekleyiniz... Yükleniyor: %{int(i / toplam * 100)}")
            time.sleep(10)
    progress_bar.progress(100)
    status_text.success("✅ Tüm veriler başarıyla çekildi.")
    analiz_ve_goster()
