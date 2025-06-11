import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import plotly.express as px

st.set_page_config(page_title="🎯 Dashboard Multi Pajak", layout="wide")
st.title("📊 Dashboard Kepatuhan Multi Jenis Pajak")
st.markdown("Upload file Excel dan pilih jenis pajak serta tahun pajak untuk mulai.")

jenis_pajak = st.selectbox("🧾 Pilih Jenis Pajak", ["HIBURAN", "MAKAN MINUM"])
uploaded_file = st.file_uploader("📁 Upload File Excel", type=["xlsx"])
tahun_pajak = st.number_input("📅 Pilih Tahun Pajak", min_value=2000, max_value=2100, value=2024)

def hitung_kepatuhan(df, tahun_pajak):
    df.columns = [str(col).upper().strip() for col in df.columns]
    df['TMT'] = pd.to_datetime(df['TMT'], errors='coerce')

    payment_cols = [
        col for col in df.columns
        if str(tahun_pajak) in str(col).lower()
        and not any(x in str(col).lower() for x in ['total', 'rata', 'jumlah', 'average'])
    ]

    total_pembayaran = df[payment_cols].sum(axis=1)

    def hitung_bulan_aktif(tmt):
        if pd.isna(tmt): return 0
        if tmt.year < tahun_pajak:
            return 12
        elif tmt.year > tahun_pajak:
            return 0
        else:
            return 12 - tmt.month + 1

    bulan_aktif = df['TMT'].apply(hitung_bulan_aktif)
    bulan_pembayaran = df[payment_cols].gt(0).sum(axis=1)
    rata_rata_pembayaran = total_pembayaran / bulan_pembayaran.replace(0, 1)
    kepatuhan_persen = bulan_pembayaran / bulan_aktif.replace(0, 1) * 100

    def klasifikasi(kepatuhan):
        if kepatuhan <= 33.333:
            return "Kurang Patuh"
        elif kepatuhan <= 66.666:
            return "Cukup Patuh"
        else:
            return "Patuh"

    klasifikasi_kepatuhan = kepatuhan_persen.apply(klasifikasi)

    df["TOTAL PEMBAYARAN"] = total_pembayaran
    df["BULAN AKTIF"] = bulan_aktif
    df["BULAN PEMBAYARAN"] = bulan_pembayaran
    df["RATA-RATA PEMBAYARAN"] = rata_rata_pembayaran
    df["KEPATUHAN (%)"] = kepatuhan_persen
    df["KLASIFIKASI KEPATUHAN"] = klasifikasi_kepatuhan

    return df, payment_cols

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    selected_sheet = st.selectbox("📄 Pilih Nama Sheet", sheet_names)
    df_input = pd.read_excel(xls, sheet_name=selected_sheet)

    original_cols = df_input.columns
    normalized_cols = [str(col).upper().strip() for col in df_input.columns]
    col_mapping = dict(zip(normalized_cols, df_input.columns))
    df_input.columns = normalized_cols

    required_cols = ["TMT", "NAMA OP", "NM UNIT"]
    if jenis_pajak == "HIBURAN":
        required_cols.append("KLASIFIKASI")

    missing_cols = [col for col in required_cols if col not in df_input.columns]

    if missing_cols:
        st.error(f"❌ Kolom wajib hilang: {', '.join(missing_cols)}. Harap periksa file Anda.")
    else:
        df_output, payment_cols = hitung_kepatuhan(df_input.copy(), tahun_pajak)

        df_output.columns = [
            col_mapping.get(col, col).title().strip() if isinstance(col_mapping.get(col, col), str) else col
            for col in df_output.columns
        ]

        with st.sidebar:
            st.header("🔍 Filter Data")
            selected_unit = st.selectbox("🏢 Pilih UPPPD", ["Semua"] + sorted(df_output["Nm Unit"].dropna().unique().tolist()))
            if selected_unit != "Semua":
                df_output = df_output[df_output["Nm Unit"] == selected_unit]

            if "Klasifikasi" in df_output.columns:
                selected_klasifikasi = st.multiselect("📂 Pilih Klasifikasi", sorted(df_output["Klasifikasi"].dropna().unique().tolist()), default=None)
                if selected_klasifikasi:
                    df_output = df_output[df_output["Klasifikasi"].isin(selected_klasifikasi)]

            if "Status" in df_output.columns:
                selected_status = st.multiselect("📌 Pilih Status WP", options=sorted(df_output["Status"].dropna().unique().tolist()), default=None)
                if selected_status:
                    df_output = df_output[df_output["Status"].isin(selected_status)]

        st.success("✅ Data berhasil diproses dan difilter!")
        st.dataframe(df_output.head(30), use_container_width=True)

        output = BytesIO()
        df_output.to_excel(output, index=False)
        st.download_button("⬇️ Download Hasil Excel", data=output.getvalue(), file_name=f"hasil_dashboard_{jenis_pajak}.xlsx")

        st.subheader("🧁 Pie Chart Kepatuhan WP")
        pie_data = df_output["Klasifikasi Kepatuhan"].value_counts().reset_index()
        pie_data.columns = ["Klasifikasi", "Jumlah"]
        fig_pie = px.pie(pie_data, names="Klasifikasi", values="Jumlah", title="Distribusi Kepatuhan WP", color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📈 Tren Pembayaran Pajak per Bulan")
        if payment_cols:
            bulanan = df_output[payment_cols].sum().reset_index()
            bulanan.columns = ["Bulan", "Total Pembayaran"]
            bulanan["Bulan"] = pd.to_datetime(bulanan["Bulan"], errors="coerce")
            bulanan = bulanan.sort_values("Bulan")
            fig_line = px.line(bulanan, x="Bulan", y="Total Pembayaran", title="Total Pembayaran Pajak per Bulan", markers=True, line_shape="spline", color_discrete_sequence=["#FFB6C1"])
            st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("🏅 Top 20 WP Berdasarkan Total Pembayaran")
        top_wp = df_output[["Nama Op", "Total Pembayaran"]].groupby("Nama Op").sum().reset_index()
        top_wp = top_wp.sort_values("Total Pembayaran", ascending=False).head(20)
        fig_bar = px.bar(top_wp, x="Nama Op", y="Total Pembayaran", title="Top 20 WP Berdasarkan Total Pembayaran", color_discrete_sequence=["#A0CED9"])
        st.plotly_chart(fig_bar, use_container_width=True)