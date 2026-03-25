import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import os
from datetime import datetime

# --- ФУНКЦИИ ---
def analyze_city_data(df, city_name):
    city_df = df[df['city'] == city_name].copy().sort_values('timestamp')
    city_df['rolling_mean'] = city_df['temperature'].rolling(window=30).mean()
    seasonal_stats = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    seasonal_stats.columns = ['season', 'mean_seasonal', 'std_seasonal']
    city_df = city_df.merge(seasonal_stats, on='season', how='left')
    city_df['is_anomaly'] = (city_df['temperature'] > city_df['mean_seasonal'] + 2 * city_df['std_seasonal']) | \
                            (city_df['temperature'] < city_df['mean_seasonal'] - 2 * city_df['std_seasonal'])
    return city_df, seasonal_stats

def get_weather_sync(city, api_key):
    url = f"https://api.openweathermap.org{city}&appid={api_key}&units=metric"
    response = requests.get(url)
    return response.json()

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Climate Monitor", layout="wide")
st.title("🌡️ Анализ температур и мониторинг погоды")

# Попытка найти файл автоматически
default_file = "temperature_data.csv"
uploaded_file = st.sidebar.file_uploader("Загрузите CSV (необязательно, если файл в репозитории)", type="csv")

# Логика выбора источника данных
df = None
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
elif os.path.exists(default_file):
    df = pd.read_csv(default_file)

# API Ключ выносим отдельно, чтобы он был виден всегда
api_key = st.sidebar.text_input("OpenWeatherMap API Key", type="password")

if df is not None:
    cities = df['city'].unique()
    selected_city = st.sidebar.selectbox("Выберите город", cities)
    
    city_data, seasonal_profiles = analyze_city_data(df, selected_city)

    # Статистика
    st.subheader(f"Анализ для города: {selected_city}")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Сезонные нормы:**")
        st.dataframe(seasonal_profiles.set_index('season'))
    
    with col2:
        # График
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['temperature'], name='Температура', opacity=0.4))
        fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['rolling_mean'], name='Тренд (30д)', line=dict(color='orange')))
        anomalies = city_data[city_data['is_anomaly']]
        fig.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'], mode='markers', name='Аномалии', marker=dict(color='red')))
        st.plotly_chart(fig, use_container_width=True)

    # Работа с API (теперь срабатывает сразу при вводе ключа)
    if api_key:
        st.divider()
        weather = get_weather_sync(selected_city, api_key)
        
        if weather.get('cod') == 200:
            current_temp = weather['main']['temp']
            
            # Определяем сезон
            month = datetime.now().month
            m_to_s = {12:"winter",1:"winter",2:"winter",3:"spring",4:"spring",5:"spring",6:"summer",7:"summer",8:"summer",9:"autumn",10:"autumn",11:"autumn"}
            curr_s = m_to_s[month]
            
            # Сравнение
            row = seasonal_profiles[seasonal_profiles['season'] == curr_s].iloc[0]
            is_normal = (row['mean_seasonal'] - 2*row['std_seasonal']) <= current_temp <= (row['mean_seasonal'] + 2*row['std_seasonal'])

            st.subheader(f"Текущая погода в {selected_city}")
            m1, m2 = st.columns(2)
            m1.metric("Градусов сейчас", f"{current_temp} °C")
            if is_normal:
                m2.success(f"Норма для сезона ({curr_s})")
            else:
                m2.error(f"Аномалия для сезона ({curr_s})!")
        else:
            st.error(f"Ошибка API: {weather.get('message')}")
else:
    st.warning("Файл данных не найден. Загрузите его через боковую панель.")
