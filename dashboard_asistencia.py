import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Configuración de la página
st.set_page_config(page_title="Control de Asistencia", layout="wide")

# --- FUNCIONES DE CARGA DE DATOS ---
def get_google_sheet_url(base_url, gid):
    return base_url.replace("/edit?usp=sharing", f"/export?format=csv&gid={gid}")

@st.cache_data
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c"
    
    # 1. Cargar Hoja de Personas (Maestro)
    url_personas = get_google_sheet_url(base_url, "538750195")
    df_personas = pd.read_csv(url_personas)
    
    # 2. Cargar Hoja de Asistencia
    url_asistencia = get_google_sheet_url(base_url, "215689985")
    df_raw = pd.read_csv(url_asistencia)
    
    # --- PROCESAMIENTO DE ASISTENCIA ---
    # Seleccionar columna C (Fecha) y E a BU (Nombres)
    # Nota: Columnas en pandas son base 0. C=2, E=4, BU=72. AB=27.
    cols_interes = [2] + [i for i in range(4, 73) if i != 27]
    df_asistencia = df_raw.iloc[:, cols_interes].copy()
    
    # Renombrar columnas usando el texto en corchetes [...]
    new_cols = {}
    for col in df_asistencia.columns:
        if col == df_asistencia.columns[0]:
            new_cols[col] = "Fecha"
        else:
            match = re.search(r'\[(.*?)\]', str(col))
            new_cols[col] = match.group(1) if match else col
    
    df_asistencia = df_asistencia.rename(columns=new_cols)
    
    # Convertir de formato ancho a largo (Tidy Data)
    df_melted = df_asistencia.melt(id_vars=["Fecha"], var_name="Nombre", value_name="Estado")
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha']).dt.date
    
    # 3. Cruzar datos con la tabla de personas
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    return df_final

# Cargar datos
try:
    df = load_data()
except Exception as e:
    st.error(f"Error al cargar los datos: {e}")
    st.stop()

# --- SIDEBAR (FILTROS) ---
st.sidebar.header("Filtros")

# Filtro de Fecha
min_date = df['Fecha'].min()
max_date = df['Fecha'].max()
fecha_sel = st.sidebar.date_input("Rango de Fechas", [min_date, max_date])

# Filtros Multiselect
def unique_sorted(col):
    return sorted(df[col].dropna().unique())

f_pais = st.sidebar.multiselect("País", unique_sorted("País"))
f_area = st.sidebar.multiselect("Área", unique_sorted("Area"))
f_equipo = st.sidebar.multiselect("Equipo", unique_sorted("Equipo"))
f_nombre = st.sidebar.multiselect("Nombre", unique_sorted("Nombre"))

# Aplicar Filtros
df_filt = df.copy()
if len(fecha_sel) == 2:
    df_filt = df_filt[(df_filt['Fecha'] >= fecha_sel[0]) & (df_filt['Fecha'] <= fecha_sel[1])]

if f_pais: df_filt = df_filt[df_filt['País'].isin(f_pais)]
if f_area: df_filt = df_filt[df_filt['Area'].isin(f_area)]
if f_equipo: df_filt = df_filt[df_filt['Equipo'].isin(f_equipo)]
if f_nombre: df_filt = df_filt[df_filt['Nombre'].isin(f_nombre)]

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Control de Asistencia")

# Métricas rápidas
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Registros", len(df_filt))
with col2:
    presentes = len(df_filt[df_filt['Estado'] == 'Presente'])
    st.metric("Presentes", presentes)
with col3:
    ausentes = len(df_filt[df_filt['Estado'] == 'OOO'])
    st.metric("En OOO", ausentes)

st.divider()

# Gráficos
c1, c2 = st.columns(2)

with c1:
    st.subheader("Distribución de Asistencia")
    fig_pie = px.pie(df_filt, names='Estado', hole=0.4, 
                     color_discrete_sequence=px.colors.qualitative.Safe)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("Asistencia por Equipo")
    # Agrupamos para ver cuántos están "Presente" o "Remoto" por equipo
    df_equipo_chart = df_filt.groupby(['Equipo', 'Estado']).size().reset_index(name='Cantidad')
    fig_bar = px.bar(df_equipo_chart, x='Equipo', y='Cantidad', color='Estado', barmode='group')
    st.plotly_chart(fig_bar, use_container_width=True)

# Tabla de Detalle
st.divider()
st.subheader("Detalle de Registros")
st.dataframe(df_filt, use_container_width=True)