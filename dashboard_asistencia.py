import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Asistencia", layout="wide")

COLOR_MAP = {
    "Presente": "#63F549",              # Verde
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
    indices_personas = [i for i in range(4, 74) if i != 27]
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
    page_icon="📖"
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

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    st.sidebar.button("Restablecer Filtros", on_click=reset_filtros, type="primary")
with col_btn2:
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()
        

fecha_sel = st.sidebar.date_input(
    "Rango de Fechas", 
    value=st.session_state.get("f_fecha", (min_date, max_date)),
    key="f_fecha", format="DD/MM/YYYY"
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

# --- NUEVA LÓGICA DE INDICADORES DE PROMEDIO ---
total_regs = len(df_filt)
if total_regs > 0:
    cant_presente = len(df_filt[df_filt['Estado'] == 'Presente'])
    cant_remoto_aut = len(df_filt[df_filt['Estado'] == 'Remoto autorizado'])
    cant_remoto_no_just = len(df_filt[df_filt['Estado'] == 'Remoto no justificado'])
    cant_ooo = len(df_filt[df_filt['Estado'] == 'OOO'])
    cant_remotos_total = cant_remoto_aut + cant_remoto_no_just
    
    # Cálculo de Promedio de Asistencia Efectiva (Presente + Remoto Autorizado) / (Total - OOO)
    total_laborable = total_regs - cant_ooo
    if total_laborable > 0:
        promedio_asistencia = ((cant_presente + cant_remoto_aut) / total_laborable) * 100
    else:
        promedio_asistencia = 0.0
        
    # Porcentajes de distribución sobre el total general
    pct_presente = (cant_presente / total_regs) * 100
    pct_remoto = (cant_remotos_total / total_regs) * 100
    pct_ooo = (cant_ooo / total_regs) * 100
else:
    cant_presente = cant_remotos_total = cant_ooo = 0
    promedio_asistencia = pct_presente = pct_remoto = pct_ooo = 0.0

# Renderizado de las 5 columnas de métricas
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Registros", f"{total_regs}")
m2.metric("🎯 Promedio Asistencia", f"{promedio_asistencia:.1f}%")
m3.metric("Presentes", f"{cant_presente} ({pct_presente:.1f}%)")
m4.metric("Remotos", f"{cant_remotos_total} ({pct_remoto:.1f}%)")
m5.metric("OOO", f"{cant_ooo} ({pct_ooo:.1f}%)")

st.markdown("---")


# Fila 1: Distribución y Equipos
c1, c2 = st.columns(2)

with c1:
    st.subheader("Distribución General")
    fig_pie = px.pie(df_filt, names='Estado', hole=0.4, color='Estado', color_discrete_map=COLOR_MAP)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("Asistencia por Equipo")
    df_bar_team = df_filt.groupby(['Equipo', 'Estado']).size().reset_index(name='Cantidad')
    fig_bar_team = px.bar(df_bar_team, x='Equipo', y='Cantidad', color='Estado', barmode='group', color_discrete_map=COLOR_MAP)
    st.plotly_chart(fig_bar_team, use_container_width=True)

# Fila 2: Gráfico por Área
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

# --- NUEVA SECCIÓN: TASA DE ASISTENCIA PROMEDIO POR EQUIPO ---
st.markdown("---")
st.subheader("📈 Tasa de Asistencia Promedio por Equipo (%)")
if total_regs > 0:
    # Definimos los estados válidos de asistencia
    df_filt['Es_Asistencia'] = df_filt['Estado'].isin(['Presente', 'Remoto autorizado'])
    # Excluimos OOO para evaluar solo días laborales reales
    df_lab = df_filt[df_filt['Estado'] != 'OOO']
    
    if not df_lab.empty:
        df_prom_equipo = df_lab.groupby('Equipo')['Es_Asistencia'].mean().reset_index()
        df_prom_equipo['% Asistencia'] = df_prom_equipo['Es_Asistencia'] * 100
        df_prom_equipo = df_prom_equipo.sort_values(by='% Asistencia', ascending=False)
        
        fig_prom = px.bar(
            df_prom_equipo, 
            x='Equipo', 
            y='% Asistencia', 
            text_auto='.1f',
            labels={'% Asistencia': 'Promedio (%)'},
            range_y=[0, 100]
        )
        st.plotly_chart(fig_prom, use_container_width=True)
    else:
        st.info("No hay suficientes datos laborales en este rango para calcular promedios por equipo (Todos están OOO).")

# Tabla de Detalle
st.markdown("---")
st.subheader("📋 Detalle de Registros")
st.dataframe(df_filt[['Fecha', 'Nombre', 'Estado', 'Area', 'Equipo', 'País']], use_container_width=True, hide_index=True)