import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import sys

st.set_page_config(page_title="AGF Web Paneli", layout="centered")
st.title("🐎 AGF Takip ve Analiz Web Paneli")

agf_url = st.text_input("TJK AGF Sayfası Linki")
saat_girdisi = st.text_input("Veri çekim saatlerini girin (örn: 14:00,15:15,16:30)")

progress_bar = st.empty()
status_text = st.empty()
tablo_holder = st.empty()

if st.button("🔍 Verileri Çek ve Analiz Et"):
    if not agf_url or not saat_girdisi:
        st.warning("Lütfen tüm alanları doldurun.")
    else:
        status_text.text("⏳ Lütfen bekleyiniz... Yükleniyor: %0")
        planlanan_cekimler = []
        for s in [x.strip() for x in saat_girdisi.split(",") if x.strip()]:
            try:
                dt = datetime.strptime(s, "%H:%M")
                planlanan_cekimler.append(dt.strftime("%H:%M"))
            except:
                st.warning(f"⚠️ Geçersiz saat formatı atlandı: {s}")

        agf_data_dict = {}

        def belirle_surpriz_tipi(row, saatler):
            try:
                agf_values = row[1:-1].dropna().astype(float)
                if len(agf_values) < 3:
                    return ""
                ilk_agf = agf_values.iloc[0]
                son_agf = agf_values.iloc[-1]
                fark_ilk_son = round(son_agf - ilk_agf, 2)
                if son_agf < 10 and fark_ilk_son >= 1.0:
                    return f"SÜRPRİZ ({row['At']} %+{fark_ilk_son})"
                if len(saatler) >= 2:
                    son1 = row[saatler[-1]]
                    son2 = row[saatler[-2]]
                    if pd.notna(son1) and pd.notna(son2):
                        fark_son_dk = round(float(son1) - float(son2), 2)
                        if fark_son_dk >= 0.3 and float(son1) < 10:
                            return f"Son DK Sürpriz ({row['At']} %+{fark_son_dk})"
            except:
                return ""
            return ""

        def render_analiz_tablosu():
            tablo_holder.empty()
            with tablo_holder.container():
                for ayak, df in agf_data_dict.items():
                    if df.dropna(how="all", axis=1).shape[1] < 3:
                        st.warning(f"⚠️ {ayak}. ayakta yeterli AGF verisi bulunamadı.")
                        continue

                    saatler = df.columns[1:].tolist()
                    last_col = df.columns[-1]
                    prev_col = df.columns[-2]

                    df[last_col] = pd.to_numeric(df[last_col], errors='coerce')
                    df[prev_col] = pd.to_numeric(df[prev_col], errors='coerce')
                    df[df.columns[1]] = pd.to_numeric(df[df.columns[1]], errors='coerce')

                    df["Sürekli Artış Göstermiş Atlar"] = df[df.columns[1:-1]].diff(axis=1).apply(
                        lambda x: sum([1 if v > 0 else -1 if v < 0 else 0 for v in x.dropna()]), axis=1
                    )
                    df["Toplam AGF Değişim %"] = df[last_col] - df[df.columns[1]]
                    df["Sabit Çok Değişmeyen AGFLER"] = df[df.columns[1:-1]].std(axis=1)
                    df["Sürpriz Tipi"] = df.apply(lambda row: belirle_surpriz_tipi(row, saatler), axis=1)

                    if df[["Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER"]].isna().all().all():
                        st.warning(f"⚠️ {ayak}. ayakta anlamlı analiz verisi yok.")
                        continue

                    st.subheader(f"📊 {ayak}. Ayak - Son Güncel Analiz")

                    max_trend = df["Sürekli Artış Göstermiş Atlar"].max()
                    max_delta = df["Toplam AGF Değişim %"].max()
                    max_vol = df["Sabit Çok Değişmeyen AGFLER"].max()
                    top3_trend = df["Sürekli Artış Göstermiş Atlar"].nlargest(4).iloc[1:]
                    top3_vol = df["Sabit Çok Değişmeyen AGFLER"].nlargest(4).iloc[1:]

                    def highlight_cell(val, column):
                        try:
                            if column == "Sürekli Artış Göstermiş Atlar":
                                if val == max_trend:
                                    return 'background-color: lightgreen; font-weight: bold'
                                elif val in top3_trend.values:
                                    return 'background-color: orange; font-weight: bold'
                            elif column == "Toplam AGF Değişim %":
                                if val == max_delta:
                                    return 'background-color: lightgreen; font-weight: bold'
                                elif val > 0.74:
                                    return 'background-color: orange; font-weight: bold'
                            elif column == "Sabit Çok Değişmeyen AGFLER":
                                if val == max_vol:
                                    return 'background-color: lightgreen; font-weight: bold'
                                elif val in top3_vol.values:
                                    return 'background-color: orange; font-weight: bold'
                        except:
                            return ''
                        return ''

                    styled_df = df[["At", "Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER", "Sürpriz Tipi"]].style\
                        .applymap(lambda v: highlight_cell(v, "Sürekli Artış Göstermiş Atlar"), subset=["Sürekli Artış Göstermiş Atlar"])\
                        .applymap(lambda v: highlight_cell(v, "Toplam AGF Değişim %"), subset=["Toplam AGF Değişim %"])\
                        .applymap(lambda v: highlight_cell(v, "Sabit Çok Değişmeyen AGFLER"), subset=["Sabit Çok Değişmeyen AGFLER"])

                    try:
                        st.dataframe(styled_df, use_container_width=True)
                    except Exception as e:
                        st.warning(f"🔁 Alternatif görüntüleme kullanıldı. (Hata: {e})")
                        st.write(df[["At", "Sürekli Artış Göstermiş Atlar", "Toplam AGF Değişim %", "Sabit Çok Değişmeyen AGFLER", "Sürpriz Tipi"]])

        def fetch_agf():
            try:
                total = len(planlanan_cekimler)
                for i, plan_time in enumerate(planlanan_cekimler):
                    while True:
                        now = datetime.now().strftime("%H:%M")
                        if now == plan_time:
                            timestamp = datetime.now().strftime("%H:%M")
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
                            percent = int(((i + 1) / total) * 100)
                            progress_bar.progress(percent)
                            status_text.text(f"⏳ Lütfen bekleyiniz... Yükleniyor: %{percent}")
                            render_analiz_tablosu()
                            break
                        time.sleep(10)

                st.success("✅ Veriler çekildi ve analiz başladı")

            except Exception as e:
                st.error(f"❌ Hata oluştu: {e}")

        fetch_agf()
