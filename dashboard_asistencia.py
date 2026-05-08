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
        df = conn.read(spreadsheet=url, worksheet="215689985")
        
        if df.empty:
            return pd.DataFrame()

        # 3. Identificar columnas de personas dinámicamente
        cols = df.columns.tolist()
        
        if "Selecciona Equipo" not in cols:
            st.error(f"No se encontró la columna 'Selecciona Equipo'.")
            return pd.DataFrame()
            
        start_idx = cols.index("Selecciona Equipo") + 1
        end_idx = cols.index("Nota") if "Nota" in cols else len(cols)
        person_cols = cols[start_idx:end_idx]
        
        # 4. Transformar a formato largo
        df_long = df.melt(
            id_vars=['Fecha', 'Selecciona Equipo'],
            value_vars=person_cols,
            var_name='Persona_Original',
            value_name='Estado'
        )
        
        # --- LIMPIEZA DE DATOS MEJORADA ---
        
        # 1. Fechas: dayfirst=True para formato DD/MM/YYYY
        df_long['Fecha'] = pd.to_datetime(df_long['Fecha'], dayfirst=True, errors='coerce')
        df_long = df_long.dropna(subset=['Fecha'])
        
        # 2. Convertir TODO a string antes de manipular para evitar el error float vs str
        df_long['Persona_Original'] = df_long['Persona_Original'].astype(str)
        df_long['Estado'] = df_long['Estado'].astype(str).str.strip()
        df_long['Selecciona Equipo'] = df_long['Selecciona Equipo'].astype(str).str.strip()

        # 3. Filtrar registros vacíos o 'nan'
        df_long = df_long[
            (df_long['Estado'] != '') & 
            (df_long['Estado'].str.lower() != 'nan') &
            (df_long['Persona_Original'].str.lower() != 'nan')
        ]
        
        # 4. Limpieza de nombres
        df_long['Nombre'] = df_long['Persona_Original'].apply(lambda x: x.split('.')[-1].strip() if '.' in x else x)
        df_long['Equipo'] = df_long['Selecciona Equipo']
        
        return df_long

    except Exception as e:
        st.error(f"Error interno en la carga de datos: {e}")
        return pd.DataFrame()

# --- LÓGICA PRINCIPAL ---
try:
    df = load_data()

    if not df.empty:
        st.title("📊 Asistencia IIS")

        st.sidebar.header("Panel de Filtros")
        
        # Manejo de fechas
        fechas_validas = df['Fecha'].sort_values()
        min_date = fechas_validas.min().to_pydatetime()
        max_date = fechas_validas.max().to_pydatetime()
        
        date_range = st.sidebar.date_input("1. Periodo", [min_date, max_date])
        
        # FILTROS CON PROTECCIÓN CONTRA NULOS (Solución al error de ordenamiento)
        equipos_unicos = sorted([e for e in df['Equipo'].unique() if e and str(e).lower() != 'nan'])
        selected_teams = st.sidebar.multiselect("2. Selecciona Equipo(s)", equipos_unicos, default=equipos_unicos)
        
        estados_posibles = sorted([est for est in df['Estado'].unique() if est and str(est).lower() != 'nan'])
        selected_status = st.sidebar.multiselect("3. Status de Asistencia", estados_posibles, default=estados_posibles)
        
        # Filtrado dinámico de nombres según equipo
        nombres_en_equipos = df[df['Equipo'].isin(selected_teams)]['Nombre'].unique()
        nombres_filtrados = sorted([n for n in nombres_en_equipos if n and str(n).lower() != 'nan'])
        selected_people = st.sidebar.multiselect("4. Personas", nombres_filtrados, default=nombres_filtrados)

        # --- APLICAR FILTROS ---
        mask = (
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
            # Métricas
            m1, m2, m3 = st.columns(3)
            m1.metric("Registros", len(df_filtered))
            m2.metric("Equipos", len(df_filtered['Equipo'].unique()))
            m3.metric("Personas", len(df_filtered['Nombre'].unique()))

            # Gráficos
            c1, c2 = st.columns(2)
            color_map = {
                "Presente": "#2ecc71", 
                "OOO": "#95a5a6",
                "Remoto autorizado": "#3498db", 
                "Remoto no justificado": "#e74c3c"
            }

            with c1:
                st.subheader("Distribución Porcentual")
                fig_pie = px.pie(df_filtered, names='Estado', hole=0.4, color='Estado', color_discrete_map=color_map)
                fig_pie.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                st.subheader("Asistencia por Equipo")
                fig_bar = px.bar(df_filtered, x='Equipo', color='Estado', barmode='group', color_discrete_map=color_map)
                st.plotly_chart(fig_bar, use_container_width=True)

            # Tabla detalle
            st.markdown("### 📋 Detalle de Registros")
            df_display = df_filtered.copy()
            df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d-%m-%Y')
            st.dataframe(
                df_display[['Fecha', 'Equipo', 'Nombre', 'Estado']].sort_values(by=['Fecha'], ascending=False),
                use_container_width=True
            )
    else:
        st.info("No se encontraron datos. Verifica la URL de Google Sheets y el nombre de la pestaña.")

except Exception as e:
    st.error(f"Error crítico en la aplicación: {e}")