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
    "Remoto no justificado": "#dc3545",              # Rojo
    "OOO": "#6c757d",                                 # Gris
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
    
    idx_submitter = 1
    idx_fecha = 2
    idx_nota = 27
    
    indices_totales = [idx_submitter, idx_fecha, idx_nota] + [i for i in range(4, df_raw_asistencia.shape[1]) if i != idx_nota]
    
    df_asistencia = df_raw_asistencia.iloc[:, indices_totales].copy()
    
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
    
    col_nota = df_asistencia[['Submitter', 'Fecha', 'Nota']].copy() if 'Nota' in df_asistencia.columns else pd.DataFrame()
    
    cols_asistencia = [c for c in df_asistencia.columns if c != 'Nota']
    df_melted = df_asistencia[cols_asistencia].melt(id_vars=["Submitter", "Fecha"], var_name="Nombre", value_name="Estado")
    
    df_melted = df_melted.dropna(subset=["Estado"])
    df_melted = df_melted[df_melted["Estado"].astype(str).str.strip() != ""]
    df_melted['Fecha'] = pd.to_datetime(df_melted['Fecha'], errors='coerce').dt.date
    df_melted = df_melted.dropna(subset=["Fecha"])
    
    if not col_nota.empty:
        col_nota['Fecha'] = pd.to_datetime(col_nota['Fecha'], errors='coerce').dt.date
        col_nota = col_nota.dropna(subset=["Fecha", "Nota"])
        col_nota = col_nota[col_nota["Nota"].astype(str).str.strip() != ""]
    
    df_final = pd.merge(df_melted, df_personas, on="Nombre", how="left")
    
    for col in ['Area', 'Equipo', 'País']:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna("No definido")
            
    return df_final, col_nota

# Cargar los datos
try:
    df, df_notas_raw = load_data()
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
st.sidebar.header("🔍 Filtros Globales")

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    st.sidebar.button("Restablecer", on_click=reset_filtros, type="primary")
with col_btn2:
    if st.sidebar.button("🔄 Actualizar"):
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

# APLICAR FILTROS GLOBALES
df_filt = df.copy()
if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
    df_filt = df_filt[(df_filt['Fecha'] >= fecha_sel[0]) & (df_filt['Fecha'] <= fecha_sel[1])]

if f_estado: df_filt = df_filt[df_filt['Estado'].isin(f_estado)]
if f_pais: df_filt = df_filt[df_filt['País'].isin(f_pais)]
if f_area: df_filt = df_filt[df_filt['Area'].isin(f_area)]
if f_equipo: df_filt = df_filt[df_filt['Equipo'].isin(f_equipo)]
if f_nombre: df_filt = df_filt[df_filt['Nombre'].isin(f_nombre)]

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📊 Panel de Control de Asistencia Híbrida")

tab_resumen, tab_semana_equipo, tab_individual, tab_tendencias, tab_cumplimiento, tab_notas = st.tabs([
    "📊 Resumen General", 
    "🗓️ Registros por Semana y Equipo",
    "👤 Ficha Individual", 
    "📈 Tendencias y Hábitos", 
    "🎯 Cumplimiento y Capacidad", 
    "📝 Notas y Justificaciones"
])

# ==========================================
# PESTAÑA 1: RESUMEN GENERAL
# ==========================================
with tab_resumen:
    total_regs = len(df_filt)

    if total_regs > 0:
        cant_presente = len(df_filt[df_filt['Estado'] == 'Presente en la oficina'])
        cant_remoto_aut = len(df_filt[df_filt['Estado'].isin(['Remoto autorizado (otra razón)', 'WFA', 'Online remoto por enfermedad'])])
        cant_remoto_no_just = len(df_filt[df_filt['Estado'] == 'Remoto no justificado'])
        cant_ooo = len(df_filt[df_filt['Estado'] == 'OOO'])
        cant_remotos_total = cant_remoto_aut + cant_remoto_no_just
        
        dias_unicos = df_filt['Fecha'].nunique()
        promedio_diario_presente = (cant_presente / dias_unicos) if dias_unicos > 0 else 0.0
            
        pct_presente = (cant_presente / total_regs) * 100
        pct_remoto = (cant_remotos_total / total_regs) * 100
        pct_ooo = (cant_ooo / total_regs) * 100
    else:
        cant_presente = cant_remotos_total = cant_ooo = 0
        promedio_diario_presente = pct_presente = pct_remoto = pct_ooo = 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Registros", f"{total_regs}")
    m2.metric("👤 Prom. Presentes/Día", f"{promedio_diario_presente:.1f}")
    m3.metric("Presentes (Total)", f"{cant_presente} ({pct_presente:.1f}%)")
    m4.metric("Remotos", f"{cant_remotos_total} ({pct_remoto:.1f}%)")
    m5.metric("OOO", f"{cant_ooo} ({pct_ooo:.1f}%)")

    st.markdown("---")

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

    st.markdown("---")
    st.subheader("🏢 Asistencia por Área")
    df_bar_area = df_filt.groupby(['Area', 'Estado']).size().reset_index(name='Cantidad')
    fig_bar_area = px.bar(df_bar_area, x='Area', y='Cantidad', color='Estado', barmode='group', color_discrete_map=COLOR_MAP)
    st.plotly_chart(fig_bar_area, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Detalle de Registros")
    st.dataframe(
        df_filt[['Fecha', 'Nombre', 'Estado', 'Area', 'Equipo', 'País']], 
        column_config={"Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")},
        use_container_width=True, hide_index=True
    )

# ==========================================
# PESTAÑA: REGISTROS POR SEMANA Y EQUIPO
# ==========================================
with tab_semana_equipo:
    st.subheader("🗓️ Control Semanal de Registros por Equipo")
    st.caption("Usa esta pestaña para verificar si algún equipo omitió realizar registros en semanas específicas.")
    
    if len(df_filt) > 0:
        df_se = df_filt.copy()
        df_se['Fecha_dt'] = pd.to_datetime(df_se['Fecha'])
        
        # Calcular la fecha del inicio de semana (Lunes)
        df_se['Inicio_Semana_dt'] = df_se['Fecha_dt'] - pd.to_timedelta(df_se['Fecha_dt'].dt.weekday, unit='D')
        
        modo_conteo = st.radio(
            "Filtrar por tipo de registro:",
            ["Todos los Estados (Evaluación de cumplimiento)", "Solo 'Presente en la oficina'"],
            horizontal=True
        )
        
        df_se_filtered = df_se.copy()
        if modo_conteo == "Solo 'Presente en la oficina'":
            df_se_filtered = df_se_filtered[df_se_filtered['Estado'] == 'Presente en la oficina']

        # 1. Obtener todas las semanas y equipos del universo filtrado (ordenados cronológicamente)
        semanas_unicas = sorted(df_se['Inicio_Semana_dt'].unique())
        equipos_unicos = sorted(df['Equipo'].unique()) if not f_equipo else sorted(f_equipo)
        
        # Crear matriz completa (MultiIndex) de todas las combinaciones posibles Semana x Equipo
        idx = pd.MultiIndex.from_product([semanas_unicas, equipos_unicos], names=['Inicio_Semana_dt', 'Equipo'])
        
        # Agrupar registros reales
        df_grouped = df_se_filtered.groupby(['Inicio_Semana_dt', 'Equipo']).size().reindex(idx, fill_value=0).reset_index(name='Registros')
        
        # Formatear la fecha como string para mantener el orden estricto de fechas en el eje X
        df_grouped['Semana_Label'] = df_grouped['Inicio_Semana_dt'].dt.strftime('%d/%m/%Y')
        semanas_ordenadas_labels = [d.strftime('%d/%m/%Y') for d in semanas_unicas]

        # Pivote para heatmap y tabla (manteniendo orden explícito de columnas)
        pivot_se = df_grouped.pivot(index='Equipo', columns='Semana_Label', values='Registros').fillna(0)
        pivot_se = pivot_se.reindex(columns=semanas_ordenadas_labels)

        # --- 1. HEATMAP MAPA DE CALOR ---
        st.markdown("---")
        st.write("#### 🟩 Mapa de Calor (Semanas Cronológicas vs. Equipos)")
        
        fig_hm_se = px.imshow(
            pivot_se,
            text_auto=True,
            color_continuous_scale="Reds_r" if modo_conteo == "Todos los Estados (Evaluación de cumplimiento)" else "Greens",
            labels=dict(x="Semana (Inicio Lunes)", y="Equipo", color="Cantidad Registros"),
            aspect="auto"
        )
        # Forzar el orden estricto cronológico en el eje X
        fig_hm_se.update_xaxes(type='category', categoryorder='array', categoryarray=semanas_ordenadas_labels, side="bottom")
        st.plotly_chart(fig_hm_se, use_container_width=True)
        
        # --- 2. GRÁFICOS COMPLEMENTARIOS ---
        st.markdown("---")
        c_se1, c_se2 = st.columns(2)
        
        with c_se1:
            st.write("#### 📊 Volumen Semanal Apilado por Equipo")
            fig_bar_se = px.bar(
                df_grouped,
                x='Semana_Label',
                y='Registros',
                color='Equipo',
                barmode='stack',
                labels={'Semana_Label': 'Semana', 'Registros': 'Cantidad'}
            )
            fig_bar_se.update_xaxes(type='category', categoryorder='array', categoryarray=semanas_ordenadas_labels)
            st.plotly_chart(fig_bar_se, use_container_width=True)
            
        with c_se2:
            st.write("#### 📈 Evolución por Equipo")
            fig_line_se = px.line(
                df_grouped,
                x='Semana_Label',
                y='Registros',
                color='Equipo',
                markers=True,
                labels={'Semana_Label': 'Semana', 'Registros': 'Cantidad'}
            )
            fig_line_se.update_xaxes(type='category', categoryorder='array', categoryarray=semanas_ordenadas_labels)
            st.plotly_chart(fig_line_se, use_container_width=True)
            
        # --- 3. TABLA RESUMEN EN ORDEN CHRONOLÓGICO ---
        st.markdown("---")
        st.write("#### 📋 Tabla Resumen de Registros por Semana (Matriz de Control)")
        st.dataframe(pivot_se, use_container_width=True)

    else:
        st.info("No hay suficiente información en el rango de fechas actual.")

# ==========================================
# PESTAÑA 3: FICHA INDIVIDUAL
# ==========================================
with tab_individual:
    st.subheader("👤 Historial e Indicadores por Colaborador")
    
    personas_disponibles = sorted(df_filt['Nombre'].unique().tolist())
    if personas_disponibles:
        col_sel, col_meta = st.columns([2, 1])
        with col_sel:
            persona_sel = st.selectbox("Seleccionar Colaborador:", personas_disponibles)
        with col_meta:
            meta_presencial = st.slider("Meta Presencial (%)", min_value=0, max_value=100, value=60)

        df_ind = df_filt[df_filt['Nombre'] == persona_sel].sort_values("Fecha", ascending=False)
        total_ind = len(df_ind)
        
        if total_ind > 0:
            pres_ind = len(df_ind[df_ind['Estado'] == 'Presente en la oficina'])
            pct_ind = (pres_ind / total_ind) * 100
            
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Registros Evaluados", f"{total_ind}")
            i2.metric("Días Presente", f"{pres_ind}")
            i3.metric("% Presencialidad", f"{pct_ind:.1f}%", delta=f"{pct_ind - meta_presencial:.1f}% vs Meta")
            i4.metric("Equipo / Área", f"{df_ind['Equipo'].iloc[0]} ({df_ind['Area'].iloc[0]})")
            
            st.markdown("---")
            c_ind1, c_ind2 = st.columns([2, 1])
            
            with c_ind1:
                st.subheader("Evolución de Estados")
                df_ind['Fecha_dt'] = pd.to_datetime(df_ind['Fecha'])
                fig_ind_line = px.scatter(
                    df_ind, x='Fecha_dt', y='Estado', color='Estado', 
                    color_discrete_map=COLOR_MAP, size_max=12
                )
                fig_ind_line.update_traces(marker=dict(size=12))
                st.plotly_chart(fig_ind_line, use_container_width=True)
            
            with c_ind2:
                st.subheader("Desglose")
                fig_ind_pie = px.pie(df_ind, names='Estado', color='Estado', color_discrete_map=COLOR_MAP, hole=0.3)
                st.plotly_chart(fig_ind_pie, use_container_width=True)
        else:
            st.info("No hay registros para la persona seleccionada en el rango filtrado.")
    else:
        st.warning("No hay colaboradores disponibles con los filtros actuales.")

# ==========================================
# PESTAÑA 4: TENDENCIAS Y HÁBITOS
# ==========================================
with tab_tendencias:
    st.subheader("📉 Evolución Semanal y Patrones de Asistencia")
    
    if len(df_filt) > 0:
        df_tend = df_filt.copy()
        df_tend['Fecha_dt'] = pd.to_datetime(df_tend['Fecha'])
        df_tend['Dia_Semana'] = df_tend['Fecha_dt'].dt.day_name()
        
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
                   'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        
        df_tend['Dia_Nombre'] = df_tend['Dia_Semana'].map(dias_es)
        dias_es_orden = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        st.write("#### 🗓️ Presencia Física por Día de la Semana y Equipo")
        df_pres = df_tend[df_tend['Estado'] == 'Presente en la oficina']
        
        if not df_pres.empty:
            df_hm = df_pres.groupby(['Equipo', 'Dia_Nombre']).size().reset_index(name='Presentes')
            df_pivot = df_hm.pivot(index='Equipo', columns='Dia_Nombre', values='Presentes').fillna(0)
            
            cols_existentes = [d for d in dias_es_orden if d in df_pivot.columns]
            df_pivot = df_pivot[cols_existentes]
            
            fig_hm = px.imshow(
                df_pivot, 
                text_auto=True, 
                color_continuous_scale="Viridis",
                labels=dict(x="Día de la Semana", y="Equipo", color="Presentes")
            )
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.info("No hay registros presenciales para generar el mapa de calor.")

        st.markdown("---")
        st.write("#### 📈 Evolución Semanal por Estado")
        df_tend['Semana'] = df_tend['Fecha_dt'] - pd.to_timedelta(df_tend['Fecha_dt'].dt.weekday, unit='D')
        df_weekly = df_tend.groupby(['Semana', 'Estado']).size().reset_index(name='Cantidad')
        
        fig_line = px.line(
            df_weekly, x='Semana', y='Cantidad', color='Estado', 
            markers=True, color_discrete_map=COLOR_MAP
        )
        fig_line.update_layout(hovermode="x unified")
        st.plotly_chart(fig_line, use_container_width=True)

# ==========================================
# PESTAÑA 5: CUMPLIMIENTO Y CAPACIDAD
# ==========================================
with tab_cumplimiento:
    st.subheader("🎯 Control de Aforo y Gestión de Cumplimiento")
    
    col_cap1, col_cap2 = st.columns(2)
    
    with col_cap1:
        st.write("#### 🏬 Aforo Diario en Oficina")
        df_aforo = df_filt[df_filt['Estado'] == 'Presente en la oficina'].groupby('Fecha').size().reset_index(name='Aforo')
        
        if not df_aforo.empty:
            capacidad_max = st.number_input("Capacidad Máxima de Oficina (Asientos):", value=50, step=5)
            fig_aforo = px.bar(df_aforo, x='Fecha', y='Aforo', title="Personas Presenciales por Día")
            fig_aforo.add_hline(y=capacidad_max, line_dash="dash", line_color="red", annotation_text="Límite Aforo")
            st.plotly_chart(fig_aforo, use_container_width=True)
        else:
            st.info("No hay datos de presencia física para evaluar aforo.")

    with col_cap2:
        st.write("#### ⚠️ Inasistencias o Remoto No Justificado")
        df_no_just = df_filt[df_filt['Estado'] == 'Remoto no justificado']
        
        if not df_no_just.empty:
            df_nj_count = df_no_just.groupby(['Nombre', 'Equipo']).size().reset_index(name='Cantidad').sort_values("Cantidad", ascending=False)
            fig_nj = px.bar(df_nj_count.head(10), x='Cantidad', y='Nombre', color='Equipo', orientation='h', title="Top 10 - Remotos No Justificados")
            st.plotly_chart(fig_nj, use_container_width=True)
        else:
            st.success("🎉 No se registraron casos de 'Remoto no justificado' en este filtro.")

# ==========================================
# PESTAÑA 6: NOTAS Y JUSTIFICACIONES
# ==========================================
with tab_notas:
    st.subheader("📝 Buscador y Registro de Justificaciones")
    
    df_notas_filt = df_notas_raw.copy()
    if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
        df_notas_filt = df_notas_filt[
            (df_notas_filt['Fecha'] >= fecha_sel[0]) & 
            (df_notas_filt['Fecha'] <= fecha_sel[1])
        ]
    
    df_notas_filt = df_notas_filt.drop_duplicates()
    
    search_term = st.text_input("🔍 Buscar en las notas (palabra clave, persona, etc.):", "")
    if search_term:
        df_notas_filt = df_notas_filt[
            df_notas_filt['Nota'].str.contains(search_term, case=False, na=False) |
            df_notas_filt['Submitter'].str.contains(search_term, case=False, na=False)
        ]

    if not df_notas_filt.empty:
        st.dataframe(
            df_notas_filt[['Submitter', 'Fecha', 'Nota']],
            column_config={
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "Submitter": st.column_config.TextColumn("Submitter"),
                "Nota": st.column_config.TextColumn("Nota")
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No se encontraron notas registradas que coincidan con los criterios.")