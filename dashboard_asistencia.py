import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Asistencia", layout="wide")

COLOR_MAP = {
    "Presente en la oficina": "#63F549",             # Verde
    "Remoto autorizado (otra razón)": "#007bff",     # Azul
    "Remoto no justificado": "#dc3545", # Rojo
    "OOO": "#6c757d",                 # Gris,
    "Online remoto por enfermedad": "#608fb8",
    "WFA": "#bfcc7c"
}

# --- FUNCIONES DE CARGA Y LIMPIEZA ---
@st.cache_data
def load_data():
    sheet_id = "1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c"
    url_asistencia = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=215689985"
    url_personas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=538750195"
    
    df_raw_asistencia = pd.read_csv(url_asistencia)
    df_personas = pd.read_csv(url_personas)
    
    # Submitter (B=1), Fecha (C=2), Nota (AB=27) y Personas (E=4 en adelante)
    idx_submitter = 1
    idx_fecha = 2
    idx_nota = 27  # Columna AB explícita
    
    # Tomamos la columna Submitter, Fecha, Nota y las columnas de personas
    indices_totales = [idx_submitter, idx_fecha, idx_nota] + [i for i in range(4, df_raw_asistencia.shape[1]) if i != idx_nota]
    
    df_asistencia = df_raw_asistencia.iloc[:, indices_totales].copy()
    
    # Limpiar nombres de columnas
    new_cols = {}
    for col in df_asistencia.columns:
        col_str = str(col).strip()
        if col == df_asistencia.columns[0]:
            new_cols[col] = "Submitter"
        elif col == df_asistencia.columns[1]:
            new_cols[col] = "Fecha"
        elif "nota" in col_str.lower():
            new_cols[col] = "Nota"
        else:
            match = re.search(r'\[(.*?)\]', col_str)
            new_cols[col] = match.group(1) if match else f"SKIP_{col}"
    
    df_asistencia = df_asistencia.rename(columns=new_cols)
    df_asistencia = df_asistencia.loc[:, ~df_asistencia.columns.str.startswith('SKIP_')]
    
    # Separar la columna 'Nota' antes de hacer melt para que no interfiera con los nombres de personas
    col_nota = df_asistencia[['Submitter', 'Fecha', 'Nota']].copy() if 'Nota' in df_asistencia.columns else pd.DataFrame()
    
    # Quitar 'Nota' de las columnas a transformar (Melt)
    cols_asistencia = [c for c in df_asistencia.columns if c != 'Nota']
    df_melted = df_asistencia[cols_asistencia].melt(id_vars=["Submitter", "Fecha"], var_name="Nombre", value_name="Estado")
    
    # Limpieza general de asistencia
    df_melted = df_melted.dropna(subset=["Estado"])
    df_melted = df_melted[df_melted["Estado"].astype(str).str.strip() != ""]
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha'], errors='coerce').dt.date
    df_melted = df_melted.dropna(subset=["Fecha"])
    
    # Limpieza de Notas
    if not col_nota.empty:
        col_nota['Fecha'] = pd.to_datetime(col_nota['Fecha'], errors='coerce').dt.date
        col_nota = col_nota.dropna(subset=["Fecha", "Nota"])
        col_nota = col_nota[col_nota["Nota"].astype(str).str.strip() != ""]
    
    # Unir asistencia con Maestro de Personas
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    for col in ['Area', 'Equipo', 'País']:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna("No definido")
            
    return df_final, col_nota

# Cargar los datos
try:
    df, df_notas_raw = load_data()
    page_icon = "📖"
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

# --- INDICADORES ---
total_regs = len(df_filt)

if total_regs > 0:
    cant_presente = len(df_filt[df_filt['Estado'] == 'Presente en la oficina'])
    cant_remoto_aut = len(df_filt[df_filt['Estado'] == 'Remoto autorizado (otra razón)']) + len(df_filt[df_filt['Estado'] == 'WFA']) + len(df_filt[df_filt['Estado'] == 'Online remoto por enfermedad'])
    cant_remoto_no_just = len(df_filt[df_filt['Estado'] == 'Remoto no justificado'])
    cant_ooo = len(df_filt[df_filt['Estado'] == 'OOO'])
    cant_remotos_total = cant_remoto_aut + cant_remoto_no_just
    
    dias_unicos = df_filt['Fecha'].nunique()
    
    if dias_unicos > 0:
        promedio_diario_presente = cant_presente / dias_unicos
    else:
        promedio_diario_presente = 0.0
        
    pct_presente = (cant_presente / total_regs) * 100
    pct_remoto = (cant_remotos_total / total_regs) * 100
    pct_ooo = (cant_ooo / total_regs) * 100
else:
    cant_presente = cant_remotos_total = cant_ooo = 0
    promedio_diario_presente = pct_presente = pct_remoto = pct_ooo = 0.0
    dias_unicos = 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Registros", f"{total_regs}")
m2.metric("👤 Promedio Presentes/Día", f"{promedio_diario_presente:.1f}")
m3.metric("Presentes (Total)", f"{cant_presente} ({pct_presente:.1f}%)")
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

# --- EVOLUCIÓN DE ESTADOS POR SEMANA ---
st.markdown("---")
st.subheader("📉 Evolución de Estados por Semana")

if total_regs > 0:
    df_evol = df_filt.copy()
    df_evol['Fecha_dt'] = pd.to_datetime(df_evol['Fecha'])
    
    df_evol['Semana'] = df_evol['Fecha_dt'] - pd.to_timedelta(df_evol['Fecha_dt'].dt.weekday, unit='D')
    df_weekly = df_evol.groupby(['Semana', 'Estado']).size().reset_index(name='Cantidad')
    
    fig_line = px.line(
        df_weekly,
        x='Semana',
        y='Cantidad',
        color='Estado',
        markers=True,
        color_discrete_map=COLOR_MAP,
        labels={'Semana': 'Fecha (Inicio de semana)', 'Cantidad': 'Total de Registros'}
    )
    
    min_date_dt = df_evol['Fecha_dt'].min().replace(day=1)
    max_date_dt = df_evol['Fecha_dt'].max()
    meses_separadores = pd.date_range(start=min_date_dt, end=max_date_dt, freq='MS')
    
    for mes in meses_separadores:
        ms_epoch = int(mes.value // 10**6)
        
        fig_line.add_vline(
            x=ms_epoch,
            line_width=1.5,
            line_dash="dash",
            line_color="rgba(150, 150, 150, 0.6)",
            annotation_text=mes.strftime("%b %Y"),
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="gray"
        )
    
    fig_line.update_layout(
        hovermode="x unified",
        legend_title="Estado",
        margin=dict(t=40, b=20, l=20, r=20)
    )
    fig_line.update_xaxes(showgrid=False, tickformat="%d/%m/%Y")
    fig_line.update_yaxes(showgrid=True, gridcolor="rgba(200, 200, 200, 0.2)")
    
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("No hay datos suficientes para mostrar la evolución semanal.")

# --- TABLA 1: DETALLE DE REGISTROS ---
st.markdown("---")
st.subheader("📋 Detalle de Registros")
st.dataframe(
    df_filt[['Fecha', 'Nombre', 'Estado', 'Area', 'Equipo', 'País']], 
    column_config={
        "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
    },
    use_container_width=True, 
    hide_index=True
)

# --- TABLA 2: DETALLE DE NOTAS ---
st.markdown("---")
st.subheader("📝 Detalle de Notas")

df_notas_filt = df_notas_raw.copy()

# Aplicar filtro de fecha sobre la tabla de notas
if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
    df_notas_filt = df_notas_filt[
        (df_notas_filt['Fecha'] >= fecha_sel[0]) & 
        (df_notas_filt['Fecha'] <= fecha_sel[1])
    ]

# Eliminar duplicados si los hubiera
df_notas_filt = df_notas_filt.drop_duplicates()

if not df_notas_filt.empty:
    st.dataframe(
        df_notas_filt[['Submitter', 'Fecha', 'Nota']],
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "Submitter": st.column_config.TextColumn("Submitter"),
            "Nota": st.column_config.TextColumn("Nota")
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No hay notas registradas para el rango de fechas seleccionado.")