import requests
import logging
import os
from datetime import datetime

def get_weather_data(lat, lng):
    """
    Fetch current weather and forecast data from OpenWeatherMap API
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        Dictionary with weather information
    """
    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY", "demo_key")
        
        if api_key == "demo_key":
            logging.warning("Using demo weather data - no API key provided")
            return get_demo_weather_data(lat, lng)
        
        # Current weather
        current_url = f"https://api.openweathermap.org/data/2.5/weather"
        current_params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'metric'
        }
        
        current_response = requests.get(current_url, params=current_params, timeout=10)
        current_data = current_response.json() if current_response.status_code == 200 else {}
        
        # 5-day forecast
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
        forecast_params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'metric'
        }
        
        forecast_response = requests.get(forecast_url, params=forecast_params, timeout=10)
        forecast_data = forecast_response.json() if forecast_response.status_code == 200 else {}
        
        # Process and return weather data
        weather_info = process_weather_data(current_data, forecast_data)
        
        logging.info(f"Weather data fetched successfully for coordinates ({lat}, {lng})")
        return weather_info
        
    except requests.RequestException as e:
        logging.error(f"Error fetching weather data: {str(e)}")
        return get_demo_weather_data(lat, lng)
    except Exception as e:
        logging.error(f"Unexpected error in weather service: {str(e)}")
        return get_demo_weather_data(lat, lng)

def process_weather_data(current_data, forecast_data):
    """
    Process raw weather API data into useful information
    
    Args:
        current_data: Current weather API response
        forecast_data: Forecast API response
    
    Returns:
        Processed weather information dictionary
    """
    weather_info = {
        'current': {},
        'forecast': [],
        'recommendations': []
    }
    
    # Process current weather
    if current_data and 'main' in current_data:
        weather_info['current'] = {
            'temperature': current_data['main'].get('temp', 0),
            'humidity': current_data['main'].get('humidity', 0),
            'pressure': current_data['main'].get('pressure', 0),
            'description': current_data['weather'][0]['description'] if current_data.get('weather') else 'Unknown',
            'wind_speed': current_data.get('wind', {}).get('speed', 0),
            'wind_direction': current_data.get('wind', {}).get('deg', 0),
            'visibility': current_data.get('visibility', 0),
            'uv_index': current_data.get('uvi', 0)
        }
        
        # Check for precipitation
        if 'rain' in current_data:
            weather_info['current']['rainfall'] = current_data['rain'].get('1h', 0)
        else:
            weather_info['current']['rainfall'] = 0
    
    # Process forecast data
    if forecast_data and 'list' in forecast_data:
        daily_forecasts = {}
        
        for item in forecast_data['list'][:15]:  # Next 5 days (3-hour intervals)
            date = datetime.fromtimestamp(item['dt']).date()
            
            if date not in daily_forecasts:
                daily_forecasts[date] = {
                    'date': date.isoformat(),
                    'temp_min': item['main']['temp'],
                    'temp_max': item['main']['temp'],
                    'rainfall': 0,
                    'humidity': item['main']['humidity'],
                    'description': item['weather'][0]['description']
                }
            
            # Update min/max temperatures
            daily_forecasts[date]['temp_min'] = min(
                daily_forecasts[date]['temp_min'], 
                item['main']['temp']
            )
            daily_forecasts[date]['temp_max'] = max(
                daily_forecasts[date]['temp_max'], 
                item['main']['temp']
            )
            
            # Accumulate rainfall
            if 'rain' in item:
                daily_forecasts[date]['rainfall'] += item['rain'].get('3h', 0)
        
        weather_info['forecast'] = list(daily_forecasts.values())[:5]
    
    # Generate weather-based recommendations
    weather_info['recommendations'] = generate_weather_recommendations(weather_info)
    
    return weather_info

def generate_weather_recommendations(weather_info):
    """
    Generate agricultural recommendations based on weather data
    
    Args:
        weather_info: Processed weather information
    
    Returns:
        List of weather-based recommendations
    """
    recommendations = []
    current = weather_info.get('current', {})
    forecast = weather_info.get('forecast', [])
    
    # Temperature-based recommendations
    temp = current.get('temperature', 20)
    if temp > 35:
        recommendations.append({
            'type': 'warning',
            'category': 'temperature',
            'message': 'High temperature alert. Increase irrigation and provide shade if possible.',
            'priority': 2
        })
    elif temp < 5:
        recommendations.append({
            'type': 'warning',
            'category': 'temperature',
            'message': 'Low temperature alert. Protect crops from frost damage.',
            'priority': 2
        })
    
    # Humidity-based recommendations
    humidity = current.get('humidity', 50)
    if humidity > 80:
        recommendations.append({
            'type': 'info',
            'category': 'humidity',
            'message': 'High humidity detected. Monitor for fungal diseases.',
            'priority': 3
        })
    elif humidity < 30:
        recommendations.append({
            'type': 'info',
            'category': 'humidity',
            'message': 'Low humidity detected. Consider increasing irrigation.',
            'priority': 3
        })
    
    # Rainfall recommendations
    rainfall = current.get('rainfall', 0)
    if rainfall > 10:
        recommendations.append({
            'type': 'info',
            'category': 'rainfall',
            'message': 'Significant rainfall detected. Monitor field drainage.',
            'priority': 3
        })
    elif rainfall == 0 and forecast:
        # Check upcoming rainfall
        upcoming_rain = sum(day.get('rainfall', 0) for day in forecast[:3])
        if upcoming_rain < 5:
            recommendations.append({
                'type': 'warning',
                'category': 'rainfall',
                'message': 'No significant rainfall expected. Plan irrigation accordingly.',
                'priority': 2
            })
    
    # Wind-based recommendations
    wind_speed = current.get('wind_speed', 0)
    if wind_speed > 15:  # m/s
        recommendations.append({
            'type': 'warning',
            'category': 'wind',
            'message': 'High wind speeds detected. Secure loose materials and check for crop damage.',
            'priority': 2
        })
    
    return recommendations

def get_demo_weather_data(lat, lng):
    """
    Return demonstration weather data when API key is not available
    
    Args:
        lat: Latitude (not used in demo)
        lng: Longitude (not used in demo)
    
    Returns:
        Demo weather data structure
    """
    return {
        'current': {
            'temperature': 24.0,
            'humidity': 65,
            'pressure': 1013,
            'description': 'partly cloudy',
            'wind_speed': 3.2,
            'wind_direction': 180,
            'visibility': 10000,
            'uv_index': 6,
            'rainfall': 0
        },
        'forecast': [
            {
                'date': '2024-01-15',
                'temp_min': 18,
                'temp_max': 26,
                'rainfall': 2.5,
                'humidity': 70,
                'description': 'light rain'
            },
            {
                'date': '2024-01-16',
                'temp_min': 20,
                'temp_max': 28,
                'rainfall': 0,
                'humidity': 60,
                'description': 'sunny'
            },
            {
                'date': '2024-01-17',
                'temp_min': 19,
                'temp_max': 27,
                'rainfall': 1.2,
                'humidity': 65,
                'description': 'partly cloudy'
            }
        ],
        'recommendations': [
            {
                'type': 'info',
                'category': 'general',
                'message': 'Weather conditions are favorable for crop growth.',
                'priority': 4
            }
        ]
    }

def get_irrigation_recommendation(weather_data, ndvi_data):
    """
    Generate irrigation recommendations based on weather and field health
    
    Args:
        weather_data: Weather information
        ndvi_data: NDVI values for field zones
    
    Returns:
        Irrigation recommendation dictionary
    """
    current = weather_data.get('current', {})
    forecast = weather_data.get('forecast', [])
    
    # Calculate irrigation need score
    irrigation_score = 0
    
    # Temperature factor
    temp = current.get('temperature', 20)
    if temp > 30:
        irrigation_score += 3
    elif temp > 25:
        irrigation_score += 2
    elif temp > 20:
        irrigation_score += 1
    
    # Humidity factor
    humidity = current.get('humidity', 50)
    if humidity < 40:
        irrigation_score += 2
    elif humidity < 60:
        irrigation_score += 1
    
    # Rainfall factor
    recent_rain = current.get('rainfall', 0)
    upcoming_rain = sum(day.get('rainfall', 0) for day in forecast[:2])
    
    if recent_rain < 2 and upcoming_rain < 5:
        irrigation_score += 3
    elif recent_rain < 5 and upcoming_rain < 10:
        irrigation_score += 1
    
    # NDVI factor (field health)
    if ndvi_data:
        avg_ndvi = sum(ndvi_data.values()) / len(ndvi_data)
        if avg_ndvi < 0.3:
            irrigation_score += 2
        elif avg_ndvi < 0.5:
            irrigation_score += 1
    
    # Generate recommendation
    if irrigation_score >= 6:
        return {
            'priority': 'high',
            'message': 'Immediate irrigation recommended',
            'frequency': 'daily',
            'duration': 'extended'
        }
    elif irrigation_score >= 4:
        return {
            'priority': 'medium',
            'message': 'Irrigation needed within 24 hours',
            'frequency': 'every 2 days',
            'duration': 'normal'
        }
    elif irrigation_score >= 2:
        return {
            'priority': 'low',
            'message': 'Monitor conditions, irrigation may be needed soon',
            'frequency': 'every 3-4 days',
            'duration': 'light'
        }
    else:
        return {
            'priority': 'none',
            'message': 'Current irrigation schedule is adequate',
            'frequency': 'as scheduled',
            'duration': 'as scheduled'
        }
