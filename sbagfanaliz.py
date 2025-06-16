import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# Web arayüz ayarları
st.set_page_config(page_title="AGF Takip ve Analiz Web Paneli", layout="centered", page_icon="😎")
st.title("🐎 AGF Takip ve Analiz Web Paneli")

# Kullanıcı girişleri
agf_url = st.text_input("TJK AGF Sayfası Linki")
saat_girdisi = st.text_input("Veri çekim saatlerini girin (14:00,15:15,16:30 gibi)")

# Veri işlemleri için değişkenler
planlanan_cekimler = []
for s in [x.strip() for x in saat_girdisi.split(",") if x.strip()]:
    try:
        dt = datetime.strptime(s, "%H:%M")
        planlanan_cekimler.append(dt.strftime("%H:%M"))
    except:
        st.warning(f"⚠️ Geçersiz saat formatı atlandı: {s}")

agf_data_dict = {}
progress_bar = st.empty()
last_analysis_container = st.empty()

# Sürpriz belirleme fonksiyonu
def belirle_surpriz_tipi(row, saatler):
    try:
        agf_values = row[1:-1].dropna().astype(float)
        if len(agf_values) < 3:
            return ""
        ilk_agf = agf_values.iloc[0]
        son_agf = agf_values.iloc[-1]
        fark = son_agf - ilk_agf
        if son_agf < 10 and fark >= 1.3:
            return "SÜRPRİZ"
        if len(saatler) >= 2:
            son1 = row[saatler[-1]]
            son2 = row[saatler[-2]]
            if pd.notna(son1) and pd.notna(son2):
                fark_son = float(son1) - float(son2)
                if fark_son >= 0.3 and float(son1) < 10:
                    return "Son DK Sürpriz"
    except:
        return ""
    return ""

# Veri çekme fonksiyonu
def fetch_agf(saat):
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
        if ayak not in agf_data_dict:
            agf_data_dict[ayak] = df
        else:
            agf_data_dict[ayak] = pd.merge(agf_data_dict[ayak], df, on="At", how="outer")

# Analiz fonksiyonu
def analyze_and_display():
    for ayak, df in agf_data_dict.items():
        df = df.dropna(how="all", axis=1)
        if df.shape[1] < 3:
            continue
        saatler = df.columns[1:]
        df["Toplam AGF Değişim %"] = df[saatler[-1]] - df[saatler[0]]
        df["Sabit Çok Değişmeyen AGFLER"] = df[saatler].std(axis=1)
        df["Sürekli Artış Göstermiş Atlar"] = df[saatler].diff(axis=1).apply(
            lambda x: sum([1 if v > 0 else -1 if v < 0 else 0 for v in x]), axis=1
        )
        df["Sürpriz Tipi"] = df.apply(lambda row: belirle_surpriz_tipi(row, saatler), axis=1)

        # Renkleme kuralları
        max_vals = {
            "Sürekli Artış Göstermiş Atlar": df["Sürekli Artış Göstermiş Atlar"].max(),
            "Toplam AGF Değişim %": df["Toplam AGF Değişim %"].max(),
            "Sabit Çok Değişmeyen AGFLER": df["Sabit Çok Değişmeyen AGFLER"].max(),
        }

        def highlight(val, col):
            if val == max_vals[col]: return "background-color: lightgreen"
            if col == "Toplam AGF Değişim %" and val > 0.74: return "background-color: orange"
            if col == "Sabit Çok Değişmeyen AGFLER" and val in sorted(df[col], reverse=True)[1:4]: return "background-color: orange"
            if col == "Sürekli Artış Göstermiş Atlar" and val in sorted(df[col], reverse=True)[1:4]: return "background-color: orange"
            return ""

        styled = df.style
        for col in ["Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER"]:
            styled = styled.applymap(lambda v: highlight(v, col), subset=[col])

        last_analysis_container.markdown(f"### 📈 {ayak}. Ayak - Son Güncel Analiz")
        last_analysis_container.dataframe(styled, use_container_width=True)

# Butona tıklandıktan sonra saatte bekleme
if st.button("🔍 Verileri Çek ve Analiz Et") and agf_url and planlanan_cekimler:
    for idx, saat in enumerate(planlanan_cekimler):
        simdi = datetime.utcnow() + timedelta(hours=3)
        simdi_str = simdi.strftime("%H:%M")
        if simdi_str >= saat:
            fetch_agf(saat)
            analyze_and_display()
            progress = int((idx + 1) / len(planlanan_cekimler) * 100)
            progress_bar.progress(progress / 100.0, text=f"Yükleniyor: %{progress}")
