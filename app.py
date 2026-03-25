import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import os
from datetime import datetime

# --- 1. ФУНКЦИИ ДЛЯ АНАЛИЗА ---

def analyze_city_data(df, city_name):
    # Фильтруем данные по выбранному городу
    city_df = df[df['city'] == city_name].copy().sort_values('timestamp')
    
    # Считаем скользящее среднее (окно 30 дней)
    city_df['rolling_mean'] = city_df['temperature'].rolling(window=30).mean()
    
    # Считаем среднее и std для каждого сезона (историческая норма)
    seasonal_stats = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    seasonal_stats.columns = ['season', 'mean_seasonal', 'std_seasonal']
    
    # Объединяем основную таблицу со статистикой сезонов
    city_df = city_df.merge(seasonal_stats, on='season', how='left')
    
    # Выявляем аномалии (выход за пределы mean ± 2*std)
    city_df['is_anomaly'] = (city_df['temperature'] > city_df['mean_seasonal'] + 2 * city_df['std_seasonal']) | \
                            (city_df['temperature'] < city_df['mean_seasonal'] - 2 * city_df['std_seasonal'])
    
    return city_df, seasonal_stats

def get_weather(city, api_key):
    # .strip() удалит случайные пробелы из города и ключа, чтобы ссылка не ломалась
    clean_city = city.strip()
    clean_key = api_key.strip()
    url = f"https://api.openweathermap.org{clean_city}&appid={clean_key}&units=metric"
    return requests.get(url).json()

# --- 2. ИНТЕРФЕЙС (STREAMLIT) ---

st.set_page_config(page_title="Мониторинг климата", layout="wide")
st.title("🌡️ Анализ температурных данных")

# Боковая панель для ввода данных
st.sidebar.header("Настройки")
uploaded_file = st.sidebar.file_uploader("Загрузите исторический CSV", type="csv")

# Пытаемся взять файл из репозитория, если пользователь ничего не загрузил
df = None
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
elif os.path.exists("temperature_data.csv"):
    df = pd.read_csv("temperature_data.csv")

# Ввод API ключа
api_key = st.sidebar.text_input("Введите API Ключ", type="password")

# Основная логика приложения
if df is not None:
    # Выбор города
    cities = df['city'].unique()
    selected_city = st.sidebar.selectbox("Выберите город для анализа", cities)
    
    # Проводим расчеты
    city_data, seasonal_profiles = analyze_city_data(df, selected_city)

    # 1. Описательная статистика
    st.subheader(f"Историческая статистика по городу {selected_city}")
    st.write(city_data[['temperature', 'rolling_mean']].describe())

    # 2. Интерактивный график
    st.subheader("Временной ряд температур")
    fig = go.Figure()
    # Линия температуры
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['temperature'], name='Температура', opacity=0.4))
    # Линия тренда
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['rolling_mean'], name='Тренд (30 дней)', line=dict(color='orange')))
    # Точки аномалий
    anomalies = city_data[city_data['is_anomaly']]
    fig.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'], mode='markers', name='Аномалии', marker=dict(color='red')))
    
    st.plotly_chart(fig, use_container_width=True)

    # 3. Сезонные профили (дополнительное исследование)
    st.subheader("Нормы по сезонам")
    st.table(seasonal_profiles.set_index('season'))

    # 4. Работа с текущей погодой через API
    if api_key:
        st.divider()
        st.subheader(f"Мониторинг текущей температуры в {selected_city}")
        
        weather_response = get_weather(selected_city, api_key)
        
        # Если API ответил успешно (код 200)
        if str(weather_response.get("cod")) == "200":
            current_temp = weather_response["main"]["temp"]
            
            # Определяем текущий сезон по месяцу
            month = datetime.now().month
            month_to_season = {12: "winter", 1: "winter", 2: "winter", 
                               3: "spring", 4: "spring", 5: "spring", 
                               6: "summer", 7: "summer", 8: "summer", 
                               9: "autumn", 10: "autumn", 11: "autumn"}
            current_season = month_to_season[month]
            
            # Сравниваем с нормой для этого сезона
            stats = seasonal_profiles[seasonal_profiles['season'] == current_season].iloc[0]
            is_normal = (stats['mean_seasonal'] - 2*stats['std_seasonal']) <= current_temp <= (stats['mean_seasonal'] + 2*stats['std_seasonal'])
            
            # Выводим результат
            col1, col2 = st.columns(2)
            col1.metric("Температура сейчас", f"{current_temp} °C")
            if is_normal:
                col2.success(f"Температура в норме для сезона {current_season}")
            else:
                col2.error(f"Аномалия! Температура вне нормы для сезона {current_season}")
        
        # Если API выдал ошибку (например, 401 - неверный ключ)
        else:
            # ТЗ: выводим весь JSON с ошибкой
            st.error(f"Ошибка API: {weather_response}")
    else:
        st.info("Введите API-ключ в боковой панели, чтобы увидеть текущую погоду.")
else:
    st.warning("Файл данных не найден. Пожалуйста, загрузите CSV файл.")
