import pandas as pd
import numpy as np
import requests
import aiohttp
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os

# Генерация данных
seasonal_temperatures = {
    "New York": {"winter": 0, "spring": 10, "summer": 25, "autumn": 15},
    "London": {"winter": 5, "spring": 11, "summer": 18, "autumn": 12},
    "Paris": {"winter": 4, "spring": 12, "summer": 20, "autumn": 13},
    "Tokyo": {"winter": 6, "spring": 15, "summer": 27, "autumn": 18},
    "Moscow": {"winter": -10, "spring": 5, "summer": 18, "autumn": 8},
    "Sydney": {"winter": 12, "spring": 18, "summer": 25, "autumn": 20},
    "Berlin": {"winter": 0, "spring": 10, "summer": 20, "autumn": 11},
    "Beijing": {"winter": -2, "spring": 13, "summer": 27, "autumn": 16},
    "Rio de Janeiro": {"winter": 20, "spring": 25, "summer": 30, "autumn": 25},
    "Dubai": {"winter": 20, "spring": 30, "summer": 40, "autumn": 30},
    "Los Angeles": {"winter": 15, "spring": 18, "summer": 25, "autumn": 20},
    "Singapore": {"winter": 27, "spring": 28, "summer": 28, "autumn": 27},
    "Mumbai": {"winter": 25, "spring": 30, "summer": 35, "autumn": 30},
    "Cairo": {"winter": 15, "spring": 25, "summer": 35, "autumn": 25},
    "Mexico City": {"winter": 12, "spring": 18, "summer": 20, "autumn": 15},
}

month_to_season = {12: "winter", 1: "winter", 2: "winter",
                   3: "spring", 4: "spring", 5: "spring",
                   6: "summer", 7: "summer", 8: "summer",
                   9: "autumn", 10: "autumn", 11: "autumn"}

def generate_realistic_temperature_data(cities, num_years=10):
    dates = pd.date_range(start="2010-01-01", periods=365 * num_years, freq="D")
    data = []
    for city in cities:
        for date in dates:
            season = month_to_season[date.month]
            mean_temp = seasonal_temperatures[city][season]
            temperature = np.random.normal(loc=mean_temp, scale=5)
            data.append({"city": city, "timestamp": date, "temperature": temperature})
    df = pd.DataFrame(data)
    df['season'] = df['timestamp'].dt.month.map(lambda x: month_to_season[x])
    return df

def ensure_data_exists():
    if not os.path.exists('temperature_data.csv'):
        print("Generating data...")
        data_gen = generate_realistic_temperature_data(list(seasonal_temperatures.keys()))
        data_gen.to_csv('temperature_data.csv', index=False)

# Фукнции анализа
def analyze_city(city_data):
    df = city_data.copy()
    df = df.sort_values('timestamp')
    
    # Скользящее среднее
    df['rolling_mean'] = df['temperature'].rolling(window=30).mean()
    df['rolling_std'] = df['temperature'].rolling(window=30).std()
    
    # Аномалии
    # Если отличается более чем на 2 стандартных отклонения, считаем аномалией
    lower_bound = df['rolling_mean'] - 2 * df['rolling_std']
    upper_bound = df['rolling_mean'] + 2 * df['rolling_std']
    
    df['is_anomaly'] = (df['temperature'] < lower_bound) | (df['temperature'] > upper_bound)
    
    seasonal_stats = df.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    
    return df, seasonal_stats

def run_analysis_sequential(df):
    results = {}
    for city in df['city'].unique():
        city_df = df[df['city'] == city]
        results[city] = analyze_city(city_df)
    return results

def run_analysis_parallel(df):
    cities = df['city'].unique()
    city_dfs = [df[df['city'] == city] for city in cities]
    with ProcessPoolExecutor() as executor:
        results_list = list(executor.map(analyze_city, city_dfs))
    return dict(zip(cities, results_list))

# API
def get_weather_sync(city, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

async def get_weather_async(city, api_key, session):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        async with session.get(url) as response:
            return await response.json()
    except Exception as e:
        return {"error": str(e)}

async def get_weather_batch_async(cities, api_key):
    async with aiohttp.ClientSession() as session:
        tasks = [get_weather_async(city, api_key, session) for city in cities]
        return await asyncio.gather(*tasks)