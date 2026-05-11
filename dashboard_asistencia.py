import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Asistencia SW IIS Chile", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = "https://docs.google.com/spreadsheets/d/1H6aWDWu-9wHbEd1iUIrb0tkIMf5S_7xkgrx7YSQbo8c/edit?usp=sharing"
        
        # 1. Leer Hoja de Asistencia (Principal)
        df = conn.read(spreadsheet=url, worksheet="215689985")
        
        # 2. Leer Hoja de Referencia (Maestro de Personas) - GID 538750195
        # Nota: worksheet puede aceptar el nombre de la hoja o el índice/GID según la implementación
        df_ref = conn.read(spreadsheet=url, worksheet="538750195") 
        
        if df.empty:
            return pd.DataFrame()

        # Identificar columnas de personas dinámicamente
        cols = df.columns.tolist()
        if "Selecciona Equipo" not in cols:
            st.error(f"No se encontró la columna 'Selecciona Equipo'.")
            return pd.DataFrame()
            
        start_idx = cols.index("Selecciona Equipo") + 1
        end_idx = cols.index("Nota") if "Nota" in cols else len(cols)
        person_cols = cols[start_idx:end_idx]
        
        # Transformar a formato largo
        df_long = df.melt(
            id_vars=['Fecha', 'Selecciona Equipo'],
            value_vars=person_cols,
            var_name='Persona_Original',
            value_name='Estado'
        )
        
        # --- LIMPIEZA DE DATOS ---
        df_long['Fecha'] = pd.to_datetime(df_long['Fecha'], dayfirst=True, errors='coerce')
        df_long = df_long.dropna(subset=['Fecha'])
        
        df_long['Persona_Original'] = df_long['Persona_Original'].astype(str)
        df_long['Estado'] = df_long['Estado'].astype(str).str.strip()
        
        # Limpieza de nombres para el cruce
        df_long['Nombre'] = df_long['Persona_Original'].apply(lambda x: x.split('.')[-1].strip() if '.' in x else x)
        df_long['Nombre'] = df_long['Nombre'].apply(lambda x: x.split('[')[-1].split(']')[0].strip() if '[' in x and ']' in x else x)
        
        # --- CRUCE CON MAESTRO DE PERSONAS (País y Área) ---
        if not df_ref.empty:
            # Asegurar que las columnas de referencia estén limpias
            df_ref.columns = df_ref.columns.str.strip()
            # Unimos los datos. Si una persona no está en la lista de referencia, tendrá valores NaN en Area, Equipo_Ref y País
            df_long = pd.merge(df_long, df_ref[['Nombre', 'Area', 'Equipo', 'País']], on='Nombre', how='left', suffixes=('', '_ref'))
        
        # Usamos el Equipo de la hoja de asistencia como base, pero tenemos País y Área disponibles
        df_long['Equipo'] = df_long['Selecciona Equipo'].astype(str).str.strip()
        
        # Filtrar registros vacíos
        df_long = df_long[
            (df_long['Estado'] != '') & 
            (df_long['Estado'].str.lower() != 'nan')
        ]
        
        return df_long

    except Exception as e:
        st.error(f"Error interno en la carga de datos: {e}")
        return pd.DataFrame()

# --- LÓGICA PRINCIPAL ---
try:
    df = load_data()

    if not df.empty:
        st.title("📊 Dashboard de Asistencia IIS")

        st.sidebar.header("Panel de Filtros")
        
        # 1. Filtro de Periodo
        fechas_validas = df['Fecha'].sort_values()
        min_date = fechas_validas.min().to_pydatetime()
        max_date = fechas_validas.max().to_pydatetime()
        date_range = st.sidebar.date_input("1. Periodo", [min_date, max_date])
        
        # --- NUEVOS FILTROS (País y Área) ---
        
        # Filtro de País
        paises_unicos = sorted([p for p in df['País'].unique() if pd.notna(p) and str(p).lower() != 'nan'])
        selected_countries = st.sidebar.multiselect("2. Filtrar por País", paises_unicos, default=paises_unicos)
        
        # Filtro de Área
        areas_unicas = sorted([a for a in df['Area'].unique() if pd.notna(a) and str(a).lower() != 'nan'])
        selected_areas = st.sidebar.multiselect("3. Filtrar por Área", areas_unicas, default=areas_unicas)

        # Filtro de Equipo (usando la columna de la hoja principal)
        equipos_unicos = sorted([e for e in df['Equipo'].unique() if e and str(e).lower() != 'nan'])
        selected_teams = st.sidebar.multiselect("4. Selecciona Equipo(s)", equipos_unicos, default=equipos_unicos)
        
        # Filtro de Status
        estados_posibles = sorted([est for est in df['Estado'].unique() if est and str(est).lower() != 'nan'])
        selected_status = st.sidebar.multiselect("5. Status de Asistencia", estados_posibles, default=estados_posibles)
        
        # Filtrado de personas (dependiente de los filtros anteriores para facilidad de uso)
        mask_personas = (
            (df['País'].isin(selected_countries)) &
            (df['Area'].isin(selected_areas)) &
            (df['Equipo'].isin(selected_teams))
        )
        nombres_filtrados = sorted(df[mask_personas]['Nombre'].unique())
        selected_people = st.sidebar.multiselect("6. Personas", nombres_filtrados, default=nombres_filtrados)

        # --- APLICAR FILTROS FINALES ---
        mask = (
            (df['País'].isin(selected_countries)) &
            (df['Area'].isin(selected_areas)) &
            (df['Equipo'].isin(selected_teams)) &
            (df['Nombre'].isin(selected_people)) & 
            (df['Estado'].isin(selected_status))
        )
        
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask = mask & (df['Fecha'].dt.date >= date_range[0]) & (df['Fecha'].dt.date <= date_range[1])
        
        df_filtered = df[mask]

        if df_filtered.empty:
            st.warning("No hay datos para los filtros seleccionados.")
        else:
            # Métricas principales
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Registros", len(df_filtered))
            m2.metric("Países", len(df_filtered['País'].unique()))
            m3.metric("Áreas", len(df_filtered['Area'].unique()))
            m4.metric("Personas", len(df_filtered['Nombre'].unique()))

            # Gráficos
            color_map = {
                "Presente": "#2ecc71", 
                "OOO": "#95a5a6",
                "Remoto autorizado": "#3498db", 
                "Remoto no justificado": "#e74c3c"
            }

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Distribución por Estado")
                fig_pie = px.pie(df_filtered, names='Estado', hole=0.4, color='Estado', color_discrete_map=color_map)
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                st.subheader("Asistencia por País")
                fig_bar_pais = px.bar(df_filtered, x='País', color='Estado', barmode='group', color_discrete_map=color_map)
                st.plotly_chart(fig_bar_pais, use_container_width=True)

            # Tabla detalle
            st.markdown("### 📋 Detalle de Registros")
            df_display = df_filtered.copy()
            df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d-%m-%Y')
            
            # Mostrar columnas relevantes incluyendo las nuevas
            st.dataframe(
                df_display[['Fecha', 'País', 'Area', 'Equipo', 'Nombre', 'Estado']].sort_values(by=['Fecha'], ascending=False),
                use_container_width=True
            )
    else:
        st.info("No se encontraron datos. Verifica la URL y las hojas del Google Sheet.")

except Exception as e:
    st.error(f"Error crítico en la aplicación: {e}")