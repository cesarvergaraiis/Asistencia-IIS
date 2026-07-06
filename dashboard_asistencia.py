# --- DASHBOARD PRINCIPAL ---
st.title("📊 Control de Asistencia")

# --- NUEVA LÓGICA DE INDICADORES (VALOR ABSOLUTO DE PRESENTES) ---
total_regs = len(df_filt)

if total_regs > 0:
    # Contamos las asistencias por estado
    cant_presente = len(df_filt[df_filt['Estado'] == 'Presente'])
    cant_remoto_aut = len(df_filt[df_filt['Estado'] == 'Remoto autorizado'])
    cant_remoto_no_just = len(df_filt[df_filt['Estado'] == 'Remoto no justificado'])
    cant_ooo = len(df_filt[df_filt['Estado'] == 'OOO'])
    cant_remotos_total = cant_remoto_aut + cant_remoto_no_just
    
    # Cantidad de días únicos con registros en el set filtrado
    dias_unicos = df_filt['Fecha'].nunique()
    
    # Promedio diario de personas "Presente" (Valor absoluto)
    if dias_unicos > 0:
        promedio_diario_presente = cant_presente / dias_unicos
    else:
        promedio_diario_presente = 0.0
        
    # Porcentajes de distribución sobre el total general (para las tarjetas)
    pct_presente = (cant_presente / total_regs) * 100
    pct_remoto = (cant_remotos_total / total_regs) * 100
    pct_ooo = (cant_ooo / total_regs) * 100
else:
    cant_presente = cant_remotos_total = cant_ooo = 0
    promedio_diario_presente = pct_presente = pct_remoto = pct_ooo = 0.0
    dias_unicos = 0

# Renderizado de las 5 columnas de métricas
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Registros", f"{total_regs}")
m2.metric("👤 Promedio Presentes/Día", f"{promedio_diario_presente:.1f}") # Valor absoluto (ej: 14.3 personas)
m3.metric("Presentes (Total)", f"{cant_presente} ({pct_presente:.1f}%)")
m4.metric("Remotos", f"{cant_remotos_total} ({pct_remoto:.1f}%)")
m5.metric("OOO", f"{cant_ooo} ({pct_ooo:.1f}%)")

st.markdown("---")