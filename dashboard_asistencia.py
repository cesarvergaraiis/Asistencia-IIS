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
        
        # 1. Leer Hoja de Asistencia (Hoja: 215689985)
        # Contiene: Fecha, Selecciona Equipo (Tu nueva clasificación), y las columnas de personas
        df = conn.read(spreadsheet=url, worksheet="215689985")
        
        # 2. Leer Hoja de Referencia (Hoja: 538750195)
        # Contiene: Nombre, Area, Equipo (Clasificación antigua/distinta), País
        df_ref = conn.read(spreadsheet=url, worksheet="538750195") 
        
        if df.empty:
            return pd.DataFrame()

        # Identificar columnas de personas dinámicamente
        cols = df.columns.tolist()
        if "Selecciona Equipo" not in cols:
            st.error(f"No se encontró la columna 'Selecciona Equipo' en la hoja de asistencia.")
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
        
        # --- LIMPIEZA ---
        df_long['Fecha'] = pd.to_datetime(df_long['Fecha'], dayfirst=True, errors='coerce')
        df_long = df_long.dropna(subset=['Fecha'])
        df_long['Estado'] = df_long['Estado'].astype(str).str.strip()
        
        # Limpieza de nombres para el cruce (Join)
        df_long['Nombre'] = df_long['Persona_Original'].apply(lambda x: x.split('.')[-1].strip() if '.' in x else x)
        df_long['Nombre'] = df_long['Nombre'].apply(lambda x: x.split('[')[-1].split(']')[0].strip() if '[' in x and ']' in x else x)
        
        # IMPORTANTE: Definimos 'Equipo' como el valor de 'Selecciona Equipo' de la hoja 215689985
        df_long['Equipo'] = df_long['Selecciona Equipo'].astype(str).str.strip()
        
        # --- CRUCE CON REFERENCIA PARA TRAER PAÍS Y ÁREA ---
        if not df_ref.empty:
            df_ref.columns = df_ref.columns.str.strip()
            # Cruzamos solo por Nombre para traer Area y País. 
            # Ignoramos la columna 'Equipo' de la hoja de referencia para no confundir.
            df_long = pd.merge(
                df_long, 
#                df_ref[['Nombre', 'Area', 'País']], 
                df_ref[['Nombre', 'Area','Equipo' , 'País']], 
                on='Nombre', 
                how='left'
            )
        
        # Filtrar registros basura
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
        st.title("📊 Dashboard de Asistencia")

        st.sidebar.header("Panel de Filtros")
        
        # 1. Filtro de Periodo
        fechas_validas = df['Fecha'].sort_values()
        min_date = fechas_validas.min().to_pydatetime()
        max_date = fechas_validas.max().to_pydatetime()
        date_range = st.sidebar.date_input("1. Periodo", [min_date, max_date])
        
        # 2. Filtro de Equipo (Viene de la hoja 215689985 - 'Selecciona Equipo')
        equipos_unicos = sorted([e for e in df['Equipo'].unique() if e and str(e).lower() != 'nan'])
        selected_teams = st.sidebar.multiselect("2. Selecciona Equipo (Hoja Principal)", equipos_unicos, default=equipos_unicos)

        # 3. Filtro de País (Viene de la hoja de referencia)
        paises_unicos = sorted([p for p in df['País'].unique() if pd.notna(p) and str(p).lower() != 'nan'])
        selected_countries = st.sidebar.multiselect("3. Filtrar por País", paises_unicos, default=paises_unicos)
        
        # 4. Filtro de Área (Viene de la hoja de referencia)
        areas_unicas = sorted([a for a in df['Area'].unique() if pd.notna(a) and str(a).lower() != 'nan'])
        selected_areas = st.sidebar.multiselect("4. Filtrar por Área", areas_unicas, default=areas_unicas)

        # 5. Filtro de Status
        estados_posibles = sorted([est for est in df['Estado'].unique() if est and str(est).lower() != 'nan'])
        selected_status = st.sidebar.multiselect("5. Status de Asistencia", estados_posibles, default=estados_posibles)
        
        # 6. Personas (Filtrado dinámico)
        mask_p = (df['Equipo'].isin(selected_teams)) & (df['País'].isin(selected_countries)) & (df['Area'].isin(selected_areas))
        nombres_disponibles = sorted(df[mask_p]['Nombre'].unique())
        selected_people = st.sidebar.multiselect("6. Personas", nombres_disponibles, default=nombres_disponibles)

        # --- APLICACIÓN DE MÁSCARA FINAL ---
        mask = (
            (df['Equipo'].isin(selected_teams)) &
            (df['País'].isin(selected_countries)) &
            (df['Area'].isin(selected_areas)) &
            (df['Nombre'].isin(selected_people)) & 
            (df['Estado'].isin(selected_status))
        )
        
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            mask = mask & (df['Fecha'].dt.date >= date_range[0]) & (df['Fecha'].dt.date <= date_range[1])
        
        df_filtered = df[mask]

        if df_filtered.empty:
            st.warning("No hay datos para los filtros seleccionados.")
        else:
            # Métricas
            cols_m = st.columns(4)
            cols_m[0].metric("Registros", len(df_filtered))
            cols_m[1].metric("Equipos", len(df_filtered['Equipo'].unique()))
            cols_m[2].metric("Países", len(df_filtered['País'].unique()))
            cols_m[3].metric("Personas", len(df_filtered['Nombre'].unique()))

            # Gráficos
            color_map = {
                "Presente": "#2ecc71", "OOO": "#95a5a6",
                "Remoto autorizado": "#3498db", "Remoto no justificado": "#e74c3c"
            }

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Distribución por Estado")
                fig_pie = px.pie(df_filtered, names='Estado', color='Estado', color_discrete_map=color_map)
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                st.subheader("Asistencia por Equipo (Nueva Clasificación)")
                fig_bar = px.bar(df_filtered, x='Equipo', color='Estado', barmode='group', color_discrete_map=color_map)
                st.plotly_chart(fig_bar, use_container_width=True)

            # Detalle
            st.markdown("### 📋 Detalle de Registros")
            df_display = df_filtered.copy()
            df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d-%m-%Y')
            st.dataframe(
                df_display[['Fecha', 'Equipo', 'País', 'Area', 'Nombre', 'Estado']].sort_values(by='Fecha', ascending=False),
                use_container_width=True
            )
    else:
        st.info("No se encontraron datos.")

except Exception as e:
    st.error(f"Error: {e}")