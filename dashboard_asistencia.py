import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Dashboard Asistencia", layout="wide")

# --- FUNCIONES DE CARGA Y LIMPIEZA ---
@st.cache_data
def load_data():
    sheet_id = "1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c"
    # URLs de exportación directa a CSV
    url_asistencia = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=215689985"
    url_personas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=538750195"
    
    # Cargar datos
    df_raw_asistencia = pd.read_csv(url_asistencia)
    df_personas = pd.read_csv(url_personas)
    
    # --- PROCESAMIENTO ASISTENCIA ---
    # Columnas: Fecha (C=2), Personas (E=4 hasta BU=72), saltando AB (27)
    indices_personas = [i for i in range(4, 73) if i != 27]
    cols_interes = [2] + indices_personas
    
    df_asistencia = df_raw_asistencia.iloc[:, cols_interes].copy()
    
    # Limpiar nombres de columnas con Regex (solo lo que está en [...])
    new_cols = {}
    for col in df_asistencia.columns:
        if col == df_asistencia.columns[0]:
            new_cols[col] = "Fecha"
        else:
            match = re.search(r'\[(.*?)\]', str(col))
            new_cols[col] = match.group(1) if match else f"SKIP_{col}"
    
    df_asistencia = df_asistencia.rename(columns=new_cols)
    # Eliminar columnas que no tenían el formato [Nombre]
    df_asistencia = df_asistencia.loc[:, ~df_asistencia.columns.str.startswith('SKIP_')]
    
    # Transformar a formato largo (Melt)
    df_melted = df_asistencia.melt(id_vars=["Fecha"], var_name="Nombre", value_name="Estado")
    
    # LIMPIEZA DE DATOS (Solo registros con datos)
    df_melted = df_melted.dropna(subset=["Estado"])
    df_melted = df_melted[df_melted["Estado"].str.strip() != ""]
    
    # Limpiar y convertir Fechas
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha'], errors='coerce').dt.date
    df_melted = df_melted.dropna(subset=["Fecha"])
    
    # 3. UNIR CON MAESTRO DE PERSONAS
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    # Llenar nulos en metadatos por si alguien no está en la lista de personas
    for col in ['Area', 'Equipo', 'País']:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna("No definido")
            
    return df_final

# Cargar los datos
try:
    df = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.info("Asegúrate de que el archivo sea público (Cualquier persona con el enlace).")
    st.stop()

# --- LÓGICA DE FILTROS Y ESTADO ---
min_date = df['Fecha'].min()
max_date = df['Fecha'].max()

# Función para restablecer filtros
def reset_filtros():
    st.session_state["f_fecha"] = (min_date, max_date)
    st.session_state["f_pais"] = []
    st.session_state["f_area"] = []
    st.session_state["f_equipo"] = []
    st.session_state["f_nombre"] = []

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtros")
st.sidebar.button("Restablecer Filtros", on_click=reset_filtros, type="primary")

# Filtros con Session State
fecha_sel = st.sidebar.date_input(
    "Rango de Fechas", 
    value=st.session_state.get("f_fecha", (min_date, max_date)),
    key="f_fecha"
)

def multiselect_filter(label, column, key):
    options = sorted(df[column].unique().tolist())
    return st.sidebar.multiselect(label, options, key=key)

f_pais = multiselect_filter("País", "País", "f_pais")
f_area = multiselect_filter("Área", "Area", "f_area")
f_equipo = multiselect_filter("Equipo", "Equipo", "f_equipo")
f_nombre = multiselect_filter("Nombre", "Nombre", "f_nombre")

# APLICAR FILTROS AL DATAFRAME
df_filt = df.copy()

if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
    df_filt = df_filt[(df_filt['Fecha'] >= fecha_sel[0]) & (df_filt['Fecha'] <= fecha_sel[1])]

if f_pais: df_filt = df_filt[df_filt['País'].isin(f_pais)]
if f_area: df_filt = df_filt[df_filt['Area'].isin(f_area)]
if f_equipo: df_filt = df_filt[df_filt['Equipo'].isin(f_equipo)]
if f_nombre: df_filt = df_filt[df_filt['Nombre'].isin(f_nombre)]

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Control de Asistencia")

# Métricas Principales
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Registros", len(df_filt))
m2.metric("Presentes", len(df_filt[df_filt['Estado'] == 'Presente']))
m3.metric("Remotos", len(df_filt[df_filt['Estado'].str.contains('Remoto', na=False)]))
m4.metric("OOO", len(df_filt[df_filt['Estado'] == 'OOO']))

st.markdown("---")

# Gráficos
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Distribución General")
    fig_pie = px.pie(
        df_filt, 
        names='Estado', 
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("Asistencia por Equipo")
    # Agrupamos para contar estados por equipo
    df_bar = df_filt.groupby(['Equipo', 'Estado']).size().reset_index(name='Cantidad')
    fig_bar = px.bar(
        df_bar, 
        x='Equipo', 
        y='Cantidad', 
        color='Estado', 
        barmode='group'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Tabla de Detalle
st.markdown("---")
st.subheader("📋 Detalle de Registros")
st.dataframe(
    df_filt[['Fecha', 'Nombre', 'Estado', 'Area', 'Equipo', 'País']], 
    use_container_width=True,
    hide_index=True
)