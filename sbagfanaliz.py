# AGF Web Paneli - Son Güncel Analiz Odaklı
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="AGF Takip ve Analiz Web Paneli", layout="centered", page_icon="😎")
st.title("\U0001f40e AGF Takip ve Analiz Web Paneli")

agf_url = st.text_input("TJK AGF Sayfası Linki")
saat_girdisi = st.text_input("Veri çekim saatlerini girin (" 
                          "örn: 14:00,15:15,16:30)")

planlanan_cekimler = []
for s in [x.strip() for x in saat_girdisi.split(",") if x.strip()]:
    try:
        dt = datetime.strptime(s, "%H:%M")
        planlanan_cekimler.append(dt.strftime("%H:%M"))
    except:
        st.warning(f"⚠️ Geçersiz saat formatı atlandı: {s}")

agf_data_dict = {}
progress_bar = st.progress(0, text="⏳ Lütfen bekleyiniz... Yükleniyor: %0")
last_analysis_container = st.empty()


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
            last_col = df.columns[-1]
            first_col = df.columns[1]

            df["Toplam AGF Değişim %"] = df[last_col] - df[first_col]
            df["Sabit Çok Değişmeyen AGFLER"] = df.iloc[:, 1:-1].std(axis=1)
            df["Sürekli Artış Göstermiş Atlar"] = df.iloc[:, 1:-1].diff(axis=1).apply(
                lambda x: sum([1 if v > 0 else -1 if v < 0 else 0 for v in x.dropna()]), axis=1)

            df = df[["At", "Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER"]]
            df = df.sort_values(by="Toplam AGF Değişim %", ascending=False)
            df.reset_index(drop=True, inplace=True)

            # Stil ayarlama
            max_cols = {
                "Sürekli Artış Göstermiş Atlar": df["Sürekli Artış Göstermiş Atlar"].max(),
                "Toplam AGF Değişim %": df["Toplam AGF Değişim %"].max(),
                "Sabit Çok Değişmeyen AGFLER": df["Sabit Çok Değişmeyen AGFLER"].max(),
            }

            def highlight(val, col):
                if val == max_cols[col]:
                    return "background-color: lightgreen"
                elif col == "Toplam AGF Değişim %" and val > 0.74:
                    return "background-color: orange"
                elif col == "Sabit Çok Değişmeyen AGFLER" and val in sorted(df[col], reverse=True)[1:4]:
                    return "background-color: orange"
                elif col == "Sürekli Artış Göstermiş Atlar" and val in sorted(df[col], reverse=True)[1:4]:
                    return "background-color: orange"
                return ""

            styled_df = df.style.applymap(lambda v: highlight(v, "Sürekli Artış Göstermiş Atlar"), subset=["Sürekli Artış Göstermiş Atlar"])
            styled_df = styled_df.applymap(lambda v: highlight(v, "Toplam AGF Değişim %"), subset=["Toplam AGF Değişim %"])
            styled_df = styled_df.applymap(lambda v: highlight(v, "Sabit Çok Değişmeyen AGFLER"), subset=["Sabit Çok Değişmeyen AGFLER"])

            last_analysis_container.markdown(f"### 📈 {ayak}. Ayak - Son Güncel Analiz")
            last_analysis_container.dataframe(styled_df, use_container_width=True)

        except Exception as e:
            st.warning(f"Analiz hatası ({ayak}. ayak): {e}")


# Otomatik şekilde saatleri kontrol et
if agf_url and planlanan_cekimler:
    now = datetime.utcnow() + timedelta(hours=3)
    now_str = now.strftime("%H:%M")
    if now_str in planlanan_cekimler:
        fetch_agf(now_str)
        planlanan_cekimler.remove(now_str)
        analyze_and_display()

    progress_percent = int((len(saat_girdisi.split(",")) - len(planlanan_cekimler)) / len(saat_girdisi.split(",")) * 100)
    progress_bar.progress(progress_percent / 100.0, text=f"⏳ Lütfen bekleyiniz... Yükleniyor: %{progress_percent}")
