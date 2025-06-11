"""
Enhanced Weather Service for FieldVision AI
Provides real-time and historical weather data for agricultural decision making
"""

import requests
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

def get_comprehensive_weather_data(lat: float, lng: float) -> Dict:
    """
    Fetch comprehensive weather data for agricultural analysis
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        Dictionary with current weather, 7-day history, and agricultural metrics
    """
    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        
        if not api_key:
            logging.error("OpenWeatherMap API key not configured")
            raise ValueError("Weather API key required for analysis")
        
        # Get current weather
        current_weather = _fetch_current_weather(lat, lng, api_key)
        
        # Get 7-day historical data
        historical_data = _fetch_historical_weather(lat, lng, api_key)
        
        # Process data for agricultural insights
        agricultural_summary = _process_agricultural_data(current_weather, historical_data)
        
        return {
            'current': current_weather,
            'historical_7_days': historical_data,
            'agricultural_summary': agricultural_summary,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error fetching weather data: {e}")
        raise

def _celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit"""
    return round((celsius * 9/5) + 32, 1)

def _fetch_current_weather(lat: float, lng: float, api_key: str) -> Dict:
    """Fetch current weather conditions"""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        'lat': lat,
        'lon': lng,
        'appid': api_key,
        'units': 'metric'
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    return {
        'temperature': _celsius_to_fahrenheit(data['main']['temp']),
        'temperature_celsius': data['main']['temp'],
        'humidity': data['main']['humidity'],
        'pressure': data['main']['pressure'],
        'wind_speed': data['wind']['speed'],
        'description': data['weather'][0]['description'],
        'rainfall_1h': data.get('rain', {}).get('1h', 0),
        'timestamp': datetime.utcnow().isoformat()
    }

def _fetch_historical_weather(lat: float, lng: float, api_key: str) -> List[Dict]:
    """Fetch 7-day historical weather data"""
    historical_data = []
    
    for days_back in range(1, 8):  # 1-7 days ago
        timestamp = int((datetime.utcnow() - timedelta(days=days_back)).timestamp())
        
        url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
        params = {
            'lat': lat,
            'lon': lng,
            'dt': timestamp,
            'appid': api_key,
            'units': 'metric'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                daily_data = data.get('data', [{}])[0]
                
                temp_data = daily_data.get('temp', {})
                temp_max_c = temp_data.get('max', 20) if isinstance(temp_data, dict) else 20
                temp_min_c = temp_data.get('min', 15) if isinstance(temp_data, dict) else 15
                
                historical_data.append({
                    'date': (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                    'temperature_max': _celsius_to_fahrenheit(temp_max_c),
                    'temperature_min': _celsius_to_fahrenheit(temp_min_c),
                    'temperature_max_celsius': temp_max_c,
                    'temperature_min_celsius': temp_min_c,
                    'humidity': daily_data.get('humidity', 60),
                    'rainfall': daily_data.get('rain', {}).get('1h', 0) or 0,
                    'wind_speed': daily_data.get('wind_speed', 5),
                    'description': daily_data.get('weather', [{}])[0].get('description', 'unknown')
                })
        except Exception as e:
            logging.warning(f"Could not fetch historical data for {days_back} days ago: {e}")
            # Fall back to using current weather API for recent days
            try:
                response = requests.get("https://api.openweathermap.org/data/2.5/weather", 
                                      params={'lat': lat, 'lon': lng, 'appid': api_key, 'units': 'metric'}, 
                                      timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    historical_data.append({
                        'date': (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                        'temperature_max': _celsius_to_fahrenheit(data['main']['temp_max']),
                        'temperature_min': _celsius_to_fahrenheit(data['main']['temp_min']),
                        'temperature_max_celsius': data['main']['temp_max'],
                        'temperature_min_celsius': data['main']['temp_min'],
                        'humidity': data['main']['humidity'],
                        'rainfall': data.get('rain', {}).get('1h', 0) or 0,
                        'wind_speed': data['wind']['speed'],
                        'description': data['weather'][0]['description']
                    })
            except:
                # Add minimal fallback data
                historical_data.append({
                    'date': (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                    'temperature_max': _celsius_to_fahrenheit(20),
                    'temperature_min': _celsius_to_fahrenheit(15),
                    'temperature_max_celsius': 20,
                    'temperature_min_celsius': 15,
                    'humidity': 60,
                    'rainfall': 0,
                    'wind_speed': 5,
                    'description': 'data unavailable'
                })
    
    return historical_data

def _process_agricultural_data(current: Dict, historical: List[Dict]) -> Dict:
    """Process weather data for agricultural insights"""
    # Calculate 7-day totals and averages
    total_rainfall_7d = sum(day.get('rainfall', 0) for day in historical)
    avg_temperature_7d = sum((day.get('temperature_max', 0) + day.get('temperature_min', 0)) / 2 for day in historical) / len(historical) if historical else 0
    avg_humidity_7d = sum(day.get('humidity', 0) for day in historical) / len(historical) if historical else 0
    
    # Drought risk assessment
    drought_risk = "low"
    if total_rainfall_7d < 5:  # Less than 5mm in 7 days
        drought_risk = "high"
    elif total_rainfall_7d < 15:  # Less than 15mm in 7 days
        drought_risk = "moderate"
    
    # Heat stress assessment (using Fahrenheit)
    heat_stress = "low"
    recent_high_temps = [day.get('temperature_max', 0) for day in historical[-3:]]  # Last 3 days
    if any(temp > 95 for temp in recent_high_temps):  # 95°F = 35°C
        heat_stress = "high"
    elif any(temp > 86 for temp in recent_high_temps):  # 86°F = 30°C
        heat_stress = "moderate"
    
    return {
        'total_rainfall_7d': round(total_rainfall_7d, 1),
        'avg_temperature_7d': round(avg_temperature_7d, 1),
        'avg_humidity_7d': round(avg_humidity_7d, 1),
        'drought_risk': drought_risk,
        'heat_stress': heat_stress,
        'growing_conditions': _assess_growing_conditions(total_rainfall_7d, avg_temperature_7d, avg_humidity_7d)
    }

def _assess_growing_conditions(rainfall: float, temperature: float, humidity: float) -> str:
    """Assess overall growing conditions (temperature in Fahrenheit)"""
    if rainfall >= 15 and 68 <= temperature <= 77 and humidity >= 60:  # 20-25°C = 68-77°F
        return "optimal"
    elif rainfall >= 10 and 59 <= temperature <= 86 and humidity >= 50:  # 15-30°C = 59-86°F
        return "good"
    elif rainfall < 5 or temperature > 95 or humidity < 40:  # 35°C = 95°F
        return "poor"
    else:
        return "fair"

# Legacy function for backward compatibility
def get_weather_data(lat, lng):
    """Legacy function - use get_comprehensive_weather_data for new implementations"""
    try:
        return get_comprehensive_weather_data(lat, lng)
    except Exception as e:
        logging.warning(f"Weather API unavailable: {e}")
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
