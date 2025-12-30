import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time
import asyncio
import logic

# Проверка/генерация данных при запуске
logic.ensure_data_exists()

st.set_page_config(page_title="Анализ Температуры", layout="wide")

st.title("🌦️ Анализ температурных данных и мониторинг погоды")

st.sidebar.header("Настройки")
uploaded_file = st.sidebar.file_uploader("Загрузить файл с данными (CSV)", type=['csv'])
api_key = st.sidebar.text_input("OpenWeatherMap API Key", type="password")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
else:
    try:
        df = pd.read_csv('temperature_data.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.sidebar.info("Используется файл данных по умолчанию (temperature_data.csv)")
    except FileNotFoundError:
        st.error("Файл данных не найден.")
        st.stop()

cities_list = df['city'].unique()
selected_city = st.sidebar.selectbox("Выберите город", cities_list)

city_df = df[df['city'] == selected_city]
analyzed_df, seasonal_stats = logic.analyze_city(city_df)

# Вкладки
tab1, tab2, tab3 = st.tabs(["📊 Исторический анализ", "🌍 Текущая погода", "⚡ Производительность"])

with tab1:
    st.subheader(f"Исторический анализ: {selected_city}")
    
    st.markdown("### Описательная статистика")
    st.dataframe(city_df.describe(include=[np.number]), use_container_width=True)

    st.markdown("### Временной ряд температур и аномалии")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=analyzed_df['timestamp'], y=analyzed_df['temperature'],
                             mode='lines', name='Температура', line=dict(color='blue', width=1)))
    fig.add_trace(go.Scatter(x=analyzed_df['timestamp'], y=analyzed_df['rolling_mean'],
                             mode='lines', name='Скользящее среднее (30d)', line=dict(color='orange')))
    
    anomalies = analyzed_df[analyzed_df['is_anomaly']]
    fig.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'],
                             mode='markers', name='Аномалии', 
                             marker=dict(color='red', size=6, symbol='x')))
    
    fig.update_layout(title=f"Температура в городе {selected_city} (2010-2020)",
                      xaxis_title="Дата", yaxis_title="Температура (°C)")
    
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Сезонные профили")
    fig_season = go.Figure()
    fig_season.add_trace(go.Bar(
        x=seasonal_stats['season'], 
        y=seasonal_stats['mean'],
        error_y=dict(type='data', array=seasonal_stats['std'], visible=True),
        name='Средняя темп. с std'
    ))
    fig_season.update_layout(title="Средняя температура и стандартное отклонение по сезонам")
    st.plotly_chart(fig_season, use_container_width=True)


with tab2:
    st.subheader(f"Мониторинг текущей погоды: {selected_city}")
    
    if not api_key:
        st.warning("Пожалуйста, введите API Key в боковой панели для получения текущей погоды.")
    else:
        current_weather = logic.get_weather_sync(selected_city, api_key)
        
        if str(current_weather.get("cod")) == "401":
            st.error(f"Ошибка авторизации API: {current_weather.get('message')}")
        elif str(current_weather.get("cod")) != "200":
             st.error(f"Ошибка получения данных: {current_weather.get('message')}")
        else:
            temp_now = current_weather['main']['temp']
            st.metric(label="Текущая температура", value=f"{temp_now} °C")
            
            current_month = pd.Timestamp.now().month
            current_season = logic.month_to_season[current_month]
            
            season_stat = seasonal_stats[seasonal_stats['season'] == current_season].iloc[0]
            mean_hist = season_stat['mean']
            std_hist = season_stat['std']
            
            st.write(f"Текущий сезон: **{current_season}**")
            st.write(f"Историческая норма для сезона: **{mean_hist:.2f} ± {2*std_hist:.2f} °C**")
            
            if mean_hist - 2*std_hist <= temp_now <= mean_hist + 2*std_hist:
                st.success("Текущая температура в пределах нормы.")
            else:
                st.error("Аномалия! Текущая температура выходит за пределы исторической нормы.")

            st.json(current_weather)


with tab3:
    st.subheader("Сравнение производительности")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Обработка данных")
        if st.button("Запустить тест обработки"):
            start_seq = time.time()
            logic.run_analysis_sequential(df)
            seq_time = time.time() - start_seq
            
            start_par = time.time()
            logic.run_analysis_parallel(df) 
            par_time = time.time() - start_par
            
            st.write(f"Последовательно: {seq_time:.4f} сек")
            st.write(f"Параллельно: {par_time:.4f} сек")

    with col2:
        st.markdown("#### API Запросы")
        if st.button("Запустить тест API"):
            if not api_key:
                st.error("Нужен API ключ!")
            else:
                cities_subset = list(cities_list)[:5]
                
                start_sync = time.time()
                for c in cities_subset:
                    logic.get_weather_sync(c, api_key)
                sync_time = time.time() - start_sync
                
                start_async = time.time()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(logic.get_weather_batch_async(cities_subset, api_key))
                async_time = time.time() - start_async
                
                st.write(f"Синхронно ({len(cities_subset)} гор.): {sync_time:.4f} сек")
                st.write(f"Асинхронно ({len(cities_subset)} гор.): {async_time:.4f} сек")
