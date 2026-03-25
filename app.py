import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import os
from datetime import datetime

# функции анализа
def analyze_city_data(df, city_name):
    # берём данные по выбранному городу
    city_df = df[df['city'] == city_name].copy().sort_values('timestamp')
    
    # счёт скользящего среднего - окно 30 дней
    city_df['rolling_mean'] = city_df['temperature'].rolling(window=30).mean()
    
    # счёт среднего и стандартного отклонения для каждого сезона
    seasonal_stats = city_df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    seasonal_stats.columns = ['season', 'mean_seasonal', 'std_seasonal']
    
    # объединяем с основной таблицей со статистикой сезонов
    city_df = city_df.merge(seasonal_stats, on='season', how='left')
    
    # аномалии - выход за пределы сезонной +/- двух отколнений
    city_df['is_anomaly'] = (city_df['temperature'] > city_df['mean_seasonal'] + 2 * city_df['std_seasonal']) | \
                            (city_df['temperature'] < city_df['mean_seasonal'] - 2 * city_df['std_seasonal'])
    
    return city_df, seasonal_stats



def get_weather(city, api_key):
    url = "https://api.openweathermap.org"
    
    # запрос
    params = {
        'q': city.strip(),
        'appid': api_key.strip(),
        'units': 'metric'
    }
    
    # заголовки, чтобы сервер не блокировал запрос от Python
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Делаем запрос с таймаутом и заголовками
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Проверяем, не пустой ли ответ (чтобы не было ошибки JSON)
        if not response.text:
            return {"cod": "error", "message": "Сервер вернул пустой ответ. Ключ еще активируется."}
            
        return response.json()
    except Exception as e:
        return {"cod": "error", "message": f"Ошибка сети: {str(e)}"}



# Интерфейс в стримлит
st.set_page_config(page_title="Мониторинг климата", layout="wide")
st.title(" Анализ температурных данных")

# Боковая панель для ввода данных
st.sidebar.header("Настройки")
uploaded_file = st.sidebar.file_uploader("Загрузите исторический CSV", type="csv")

# Пытаемся взять файл из репозитория, если пользователь ничего не загрузил
df = None
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
elif os.path.exists("temperature_data.csv"):
    df = pd.read_csv("temperature_data.csv")

# ввод API ключа
api_key = st.sidebar.text_input("Введите API Ключ", type="password")

# основная логика
if df is not None:
    # Выбор города
    cities = df['city'].unique()
    selected_city = st.sidebar.selectbox("Выберите город для анализа", cities)
    
    # расчёты
    city_data, seasonal_profiles = analyze_city_data(df, selected_city)

    # статистика
    st.subheader(f"Историческая статистика по городу {selected_city}")
    st.write(city_data[['temperature', 'rolling_mean']].describe())

    # график
    st.subheader("Временной ряд температур")
    fig = go.Figure()
    # линия температуры
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['temperature'], name='Температура', opacity=0.4))
    # линия тренда
    fig.add_trace(go.Scatter(x=city_data['timestamp'], y=city_data['rolling_mean'], name='Тренд (30 дней)', line=dict(color='orange')))
    # точки аномалий
    anomalies = city_data[city_data['is_anomaly']]
    fig.add_trace(go.Scatter(x=anomalies['timestamp'], y=anomalies['temperature'], mode='markers', name='Аномалии', marker=dict(color='red')))
    
    st.plotly_chart(fig, use_container_width=True)

    # сезоны
    st.subheader("Нормы по сезонам")
    st.table(seasonal_profiles.set_index('season'))

    # текущая погода через API
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
            
            # сравниваем с нормой для этого сезона
            stats = seasonal_profiles[seasonal_profiles['season'] == current_season].iloc[0]
            is_normal = (stats['mean_seasonal'] - 2*stats['std_seasonal']) <= current_temp <= (stats['mean_seasonal'] + 2*stats['std_seasonal'])
            
            # вывод
            col1, col2 = st.columns(2)
            col1.metric("Температура сейчас", f"{current_temp} °C")
            if is_normal:
                col2.success(f"Температура в норме для сезона {current_season}")
            else:
                col2.error(f"Аномалия! Температура вне нормы для сезона {current_season}")
        
        # если API выдал ошибку
        else:
            # выводим весь ответ
            st.error(f"Ошибка API: {weather_response}")
    else:
        st.info("Введите API-ключ в боковой панели, чтобы увидеть текущую погоду.")
else:
    st.warning("Файл данных не найден. Пожалуйста, загрузите CSV файл.")
