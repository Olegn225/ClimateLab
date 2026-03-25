import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import asyncio
import aiohttp
from datetime import datetime

# --- ФУНКЦИИ АНАЛИЗА ---
def analyze_city_data(df, city_name):
    city_df = df[df['city'] == city_name].copy().sort_values('timestamp')
    city_df['rolling_mean'] = city_df['temperature'].rolling(window=30).mean()
    
    # Статистика по сезонам
    seasonal_stats = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    seasonal_stats.columns = ['season', 'mean_seasonal', 'std_seasonal']
    
    city_df = city_df.merge(seasonal_stats, on='season', how='left')
    city_df['is_anomaly'] = (city_df['temperature'] > city_df['mean_seasonal'] + 2 * city_df['std_seasonal']) | \
                            (city_df['temperature'] < city_df['mean_seasonal'] - 2 * city_df['std_seasonal'])
    return city_df, seasonal_stats

# --- API РАБОТА ---
def get_weather_sync(city, api_key):
    url = f"https://api.openweathermap.org{city}&appid={api_key}&units=metric"
    response = requests.get(url)
    return response.json()

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="Climate Monitor", layout="wide")
st.title("🌡️ Анализ температур и мониторинг погоды")

# 1. Загрузка данных
st.sidebar.header("Настройки")
uploaded_file = st.sidebar.file_uploader("Загрузите исторические данные (CSV)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    cities = df['city'].unique()
    
    selected_city = st.sidebar.selectbox("Выберите город", cities)
    api_key = st.sidebar.text_input("OpenWeatherMap API Key", type="password")

    # Проведение анализа
    city_data, seasonal_profiles = analyze_city_data(df, selected_city)

    # Вывод статистики
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Исторические данные: {selected_city}")
        st.write(city_data[['temperature', 'rolling_mean']].describe())
    
    with col2:
        st.subheader("Сезонные профили")
        st.dataframe(seasonal_profiles.set_index('season'))

    # График временного ряда
    st.subheader("Временной ряд с аномалиями")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['temperature'], name='Температура', line=dict(color='lightblue', width=1)))
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['rolling_mean'], name='Скользящее среднее (30д)', line=dict(color='orange', width=2)))
    
    anomalies = city_data[city_data['is_anomaly']]
    fig.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'], mode='markers', name='Аномалии', marker=dict(color='red', size=4)))
    
    st.plotly_chart(fig, use_container_width=True)

    # Текущая погода
    if api_key:
        st.divider()
        weather = get_weather_sync(selected_city, api_key)
        
        if weather.get('cod') == 200:
            current_temp = weather['main']['temp']
            
            # Определяем текущий сезон для сравнения
            month = datetime.now().month
            month_to_season = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 
                               6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
            curr_season_name = month_to_season[month]
            
            # Получаем норму для этого сезона
            season_norm = seasonal_profiles[seasonal_profiles['season'] == curr_season_name].iloc[0]
            mean_s = season_norm['mean_seasonal']
            std_s = season_norm['std_seasonal']
            
            is_normal = (mean_s - 2*std_s) <= current_temp <= (mean_s + 2*std_s)

            st.subheader(f"Текущая погода в {selected_city}")
            c1, c2 = st.columns(2)
            c1.metric("Температура сейчас", f"{current_temp} °C")
            
            if is_normal:
                c2.success(f"Температура в норме для сезона ({curr_season_name})")
            else:
                c2.error(f"Аномальная температура для сезона ({curr_season_name})!")
                st.info(f"Историческая норма: {mean_s:.2f} °C ± {2*std_s:.2f}")
        else:
            st.error(f"Ошибка API: {weather.get('message', 'Неизвестная ошибка')}")
    else:
        st.warning("Введите API ключ в боковом меню для получения текущей погоды.")
else:
    st.info("Пожалуйста, загрузите CSV файл с данными в боковом меню.")
