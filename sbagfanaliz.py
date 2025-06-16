
# AGF Takip ve Analiz Web Paneli - Full Entegre
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ----------------- SAYFA AYARI -----------------
st.set_page_config(page_title="AGF Takip ve Analiz", layout="centered", page_icon="🐎")
st.title("🐎 AGF Takip ve Analiz Web Paneli")

# ----------------- KULLANICI GİRİŞİ -----------------
agf_url = st.text_input("TJK AGF Sayfası Linki")
saat_girdisi = st.text_input("Veri çekim saatlerini girin (örn: 14:00,15:15,16:30)")
baslat = st.button("🔍 Verileri Çek ve Analiz Et")

# ----------------- HAZIRLIK -----------------
agf_data_dict = {}
progress_bar = st.empty()
last_analysis_container = st.empty()

def belirle_surpriz(row, saatler):
    try:
        agf_values = row[1:-1].dropna().astype(float)
        if len(agf_values) < 3:
            return ""
        ilk_agf = agf_values.iloc[0]
        son_agf = agf_values.iloc[-1]
        fark_ilk_son = son_agf - ilk_agf

        if son_agf < 10 and fark_ilk_son >= 1.0:
            return f"SÜRPRİZ (+{fark_ilk_son:.2f})"

        if len(saatler) >= 2:
            son1 = row[saatler[-1]]
            son2 = row[saatler[-2]]
            if pd.notna(son1) and pd.notna(son2):
                fark_son_dk = float(son1) - float(son2)
                if fark_son_dk >= 0.3 and float(son1) < 10:
                    return f"Son DK Sürpriz (+{fark_son_dk:.2f})"
    except:
        return ""
    return ""

def fetch_agf(saat):
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
            df = pd.DataFrame(current_data, columns=["At", saat])
            if ayak not in agf_data_dict or agf_data_dict[ayak].empty:
                agf_data_dict[ayak] = df
            else:
                agf_data_dict[ayak] = pd.merge(agf_data_dict[ayak], df, on="At", how="outer")
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")

def analyze_and_display():
    for ayak, df in agf_data_dict.items():
        df = df.dropna(how="all", axis=1)
        if df.shape[1] < 3:
            continue

        try:
            saatler = df.columns[1:].tolist()
            last_col = df.columns[-1]
            first_col = df.columns[1]

            df["Toplam AGF Değişim %"] = df[last_col] - df[first_col]
            df["Sabit Çok Değişmeyen AGFLER"] = df.iloc[:, 1:-1].std(axis=1)
            df["Sürekli Artış Göstermiş Atlar"] = df.iloc[:, 1:-1].diff(axis=1).apply(
                lambda x: sum([1 if v > 0 else -1 if v < 0 else 0 for v in x.dropna()]), axis=1)
            df["Sürpriz Tipi"] = df.apply(lambda row: belirle_surpriz(row, saatler), axis=1)

            df = df[["At", "Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER", "Sürpriz Tipi"]]
            df = df.sort_values(by="Toplam AGF Değişim %", ascending=False).reset_index(drop=True)

            # Renklendirme
            max_vals = {
                "Sürekli Artış Göstermiş Atlar": df["Sürekli Artış Göstermiş Atlar"].max(),
                "Toplam AGF Değişim %": df["Toplam AGF Değişim %"].max(),
                "Sabit Çok Değişmeyen AGFLER": df["Sabit Çok Değişmeyen AGFLER"].max(),
            }

            def highlight(val, col):
                if val == max_vals[col]:
                    return "background-color: lightgreen"
                elif col == "Toplam AGF Değişim %" and val > 0.74 and val != max_vals[col]:
                    return "background-color: orange"
                elif col in ["Sabit Çok Değişmeyen AGFLER", "Sürekli Artış Göstermiş Atlar"]:
                    top_vals = sorted(df[col], reverse=True)[1:4]
                    if val in top_vals:
                        return "background-color: orange"
                return ""

            styled_df = df.style                .applymap(lambda v: highlight(v, "Sürekli Artış Göstermiş Atlar"), subset=["Sürekli Artış Göstermiş Atlar"])                .applymap(lambda v: highlight(v, "Toplam AGF Değişim %"), subset=["Toplam AGF Değişim %"])                .applymap(lambda v: highlight(v, "Sabit Çok Değişmeyen AGFLER"), subset=["Sabit Çok Değişmeyen AGFLER"])

            last_analysis_container.markdown(f"### 📈 {ayak}. Ayak - Son Güncel Analiz")
            last_analysis_container.dataframe(styled_df, use_container_width=True)

        except Exception as e:
            st.warning(f"Analiz hatası ({ayak}. ayak): {e}")

# ----------------- ANA BUTON -----------------
if baslat and agf_url and saat_girdisi:
    saat_listesi = [s.strip() for s in saat_girdisi.split(",") if s.strip()]
    toplam = len(saat_listesi)
    for i, saat in enumerate(saat_listesi):
        fetch_agf(saat)
        progress_bar.progress((i + 1) / toplam, text=f"⏳ Lütfen bekleyiniz... Yükleniyor: %{int((i + 1) / toplam * 100)}")
    analyze_and_display()
