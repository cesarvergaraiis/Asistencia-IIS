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
    sheet_id = "1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c"
    url_asistencia = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=215689985"
    url_personas = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=538750195"
    
    # 1. Cargar datos
    df_personas = pd.read_csv(url_personas)
    df_raw = pd.read_csv(url_asistencia)
    
    # 2. Selección de columnas: Fecha (C=2) y Personas (E=4 a BU=72, saltando AB=27)
    # Usamos iloc para mayor precisión con los índices
    cols_idx = [2] + [i for i in range(4, 73) if i != 27]
    df_asistencia = df_raw.iloc[:, cols_idx].copy()
    
    # 3. Limpiar nombres de columnas (Extraer texto en corchetes)
    new_cols = {}
    for col in df_asistencia.columns:
        if col == df_asistencia.columns[0]:
            new_cols[col] = "Fecha"
        else:
            match = re.search(r'\[(.*?)\]', str(col))
            # Si hay corchetes, usamos el interior. Si no, ignoramos la columna o usamos el nombre original
            new_cols[col] = match.group(1) if match else f"Eliminar_{col}"
    
    df_asistencia = df_asistencia.rename(columns=new_cols)
    
    # Eliminar columnas que no tenían corchetes (si las hubiera)
    df_asistencia = df_asistencia.loc[:, ~df_asistencia.columns.str.startswith('Eliminar_')]

    # 4. Transformar a formato largo (Melt)
    df_melted = df_asistencia.melt(id_vars=["Fecha"], var_name="Nombre", value_name="Estado")
    
    # --- LIMPIEZA DE NULOS (Tu solicitud) ---
    # Eliminamos filas donde el Estado sea nulo o esté vacío
    df_melted = df_melted.dropna(subset=["Estado"])
    df_melted = df_melted[df_melted["Estado"].str.strip() != ""]
    
    # Limpiar fechas nulas y convertir a objeto date
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha'], errors='coerce').dt.date
    df_melted = df_melted.dropna(subset=["Fecha"])
    
    # 5. Cruzar con maestro de personas
    # Esto añadirá Area, Equipo y País a cada registro de asistencia
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    # Opcional: Si una persona marcó asistencia pero no está en el maestro, 
    # podemos llenar sus datos como "Sin asignar"
    df_final[['Area', 'Equipo', 'País']] = df_final[['Area', 'Equipo', 'País']].fillna("No definido")
    
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