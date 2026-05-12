import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Dashboard Asistencia", layout="wide")

COLOR_MAP = {
    "Presente": "#28a745",              # Verde
    "Remoto autorizado": "#007bff",     # Azul
    "Remoto no justificado": "#dc3545", # Rojo
    "OOO": "#6c757d"                    # Gris
}

# --- FUNCIONES DE CARGA Y LIMPIEZA ---
@st.cache_data
def load_data():
    sheet_id = "1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c"
    url_asistencia = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=215689985"
    url_personas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=538750195"
    
    df_raw_asistencia = pd.read_csv(url_asistencia)
    df_personas = pd.read_csv(url_personas)
    
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
    df_asistencia = df_asistencia.loc[:, ~df_asistencia.columns.str.startswith('SKIP_')]
    
    # Transformar a formato largo (Melt)
    df_melted = df_asistencia.melt(id_vars=["Fecha"], var_name="Nombre", value_name="Estado")
    
    # LIMPIEZA DE DATOS
    df_melted = df_melted.dropna(subset=["Estado"])
    df_melted = df_melted[df_melted["Estado"].str.strip() != ""]
    
    # Limpiar y convertir Fechas
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha'], errors='coerce').dt.date
    df_melted = df_melted.dropna(subset=["Fecha"])
    
    # UNIR CON MAESTRO DE PERSONAS
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    for col in ['Area', 'Equipo', 'País']:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna("No definido")
            
    return df_final

# Cargar los datos
try:
    df = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- LÓGICA DE FILTROS Y ESTADO ---
min_date = df['Fecha'].min()
max_date = df['Fecha'].max()

def reset_filtros():
    st.session_state["f_fecha"] = (min_date, max_date)
    st.session_state["f_pais"] = []
    st.session_state["f_area"] = []
    st.session_state["f_equipo"] = []
    st.session_state["f_nombre"] = []
    st.session_state["f_estado"] = []

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtros")
st.sidebar.button("Restablecer Filtros", on_click=reset_filtros, type="primary")

fecha_sel = st.sidebar.date_input(
    "Rango de Fechas", 
    value=st.session_state.get("f_fecha", (min_date, max_date)),
    key="f_fecha"
)

def multiselect_filter(label, column, key):
    options = sorted(df[column].unique().tolist())
    return st.sidebar.multiselect(label, options, key=key)

f_estado = multiselect_filter("Estado de Asistencia", "Estado", "f_estado")
f_pais = multiselect_filter("País", "País", "f_pais")
f_area = multiselect_filter("Área", "Area", "f_area")
f_equipo = multiselect_filter("Equipo", "Equipo", "f_equipo")
f_nombre = multiselect_filter("Nombre", "Nombre", "f_nombre")

# APLICAR FILTROS
df_filt = df.copy()
if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
    df_filt = df_filt[(df_filt['Fecha'] >= fecha_sel[0]) & (df_filt['Fecha'] <= fecha_sel[1])]

if f_estado: df_filt = df_filt[df_filt['Estado'].isin(f_estado)]
if f_pais: df_filt = df_filt[df_filt['País'].isin(f_pais)]
if f_area: df_filt = df_filt[df_filt['Area'].isin(f_area)]
if f_equipo: df_filt = df_filt[df_filt['Equipo'].isin(f_equipo)]
if f_nombre: df_filt = df_filt[df_filt['Nombre'].isin(f_nombre)]

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Control de Asistencia")

# Métricas
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Registros", len(df_filt))
m2.metric("Presentes", len(df_filt[df_filt['Estado'] == 'Presente']))
m3.metric("Remotos", len(df_filt[df_filt['Estado'].str.contains('Remoto', na=False)]))
m4.metric("OOO", len(df_filt[df_filt['Estado'] == 'OOO']))

st.markdown("---")

# Fila 1: Distribución y Equipos
c1, c2 = st.columns(2)

with c1:
    st.subheader("Distribución General")
    fig_pie = px.pie(df_filt, names='Estado', hole=0.4,color='Estado', color_discrete_map=COLOR_MAP)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("Asistencia por Equipo")
    df_bar_team = df_filt.groupby(['Equipo', 'Estado']).size().reset_index(name='Cantidad')
    fig_bar_team = px.bar(df_bar_team, x='Equipo', y='Cantidad', color='Estado', barmode='group',color_discrete_map=COLOR_MAP)
    st.plotly_chart(fig_bar_team, use_container_width=True)

# Fila 2: Gráfico por Área (Nuevo)
st.markdown("---")
st.subheader("🏢 Asistencia por Área")
df_bar_area = df_filt.groupby(['Area', 'Estado']).size().reset_index(name='Cantidad')
fig_bar_area = px.bar(
    df_bar_area, 
    x='Area', 
    y='Cantidad', 
    color='Estado', 
    barmode='group',
    color_discrete_map=COLOR_MAP
)
st.plotly_chart(fig_bar_area, use_container_width=True)

# Tabla de Detalle
st.markdown("---")
st.subheader("📋 Detalle de Registros")
st.dataframe(df_filt[['Fecha', 'Nombre', 'Estado', 'Area', 'Equipo', 'País']], use_container_width=True, hide_index=True)