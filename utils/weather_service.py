"""
Weather service for agricultural analysis
Fetches current and historical weather data for field locations
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class WeatherService:
    """Service for fetching weather data using OpenWeatherMap API"""
    
    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
        self.base_url = 'https://api.openweathermap.org/data/2.5'
        
    def get_current_weather(self, lat: float, lng: float) -> Optional[Dict]:
        """
        Fetch current weather conditions for given coordinates
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Weather data dictionary or None if request fails
        """
        if not self.api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return None
            
        try:
            url = f"{self.base_url}/weather"
            params = {
                'lat': lat,
                'lon': lng,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'temperature': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'wind_direction': data['wind'].get('deg', 0),
                'description': data['weather'][0]['description'],
                'visibility': data.get('visibility', 0) / 1000,  # Convert to km
                'clouds': data['clouds']['all'],
                'feels_like': data['main']['feels_like'],
                'temp_min': data['main']['temp_min'],
                'temp_max': data['main']['temp_max'],
                'sunrise': datetime.fromtimestamp(data['sys']['sunrise']),
                'sunset': datetime.fromtimestamp(data['sys']['sunset']),
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch current weather: {e}")
            return None
    
    def get_weather_forecast(self, lat: float, lng: float, days: int = 5) -> Optional[List[Dict]]:
        """
        Fetch weather forecast for given coordinates
        
        Args:
            lat: Latitude
            lng: Longitude
            days: Number of days to forecast (max 5 for free tier)
            
        Returns:
            List of forecast data or None if request fails
        """
        if not self.api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return None
            
        try:
            url = f"{self.base_url}/forecast"
            params = {
                'lat': lat,
                'lon': lng,
                'appid': self.api_key,
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day (every 3 hours)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            forecasts = []
            
            for item in data['list']:
                forecasts.append({
                    'datetime': datetime.fromtimestamp(item['dt']),
                    'temperature': item['main']['temp'],
                    'humidity': item['main']['humidity'],
                    'pressure': item['main']['pressure'],
                    'wind_speed': item['wind']['speed'],
                    'wind_direction': item['wind'].get('deg', 0),
                    'description': item['weather'][0]['description'],
                    'clouds': item['clouds']['all'],
                    'rain': item.get('rain', {}).get('3h', 0),
                    'snow': item.get('snow', {}).get('3h', 0)
                })
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Failed to fetch weather forecast: {e}")
            return None
    
    def get_historical_weather(self, lat: float, lng: float, days_back: int = 30) -> Optional[List[Dict]]:
        """
        Get historical weather data for analysis
        Note: This requires a paid OpenWeatherMap subscription for historical data
        For now, we'll return recent forecast data as a substitute
        
        Args:
            lat: Latitude
            lng: Longitude
            days_back: Number of days to look back
            
        Returns:
            Historical weather data or None
        """
        # For now, return current conditions as historical data
        # In production, this would use the historical weather API
        current = self.get_current_weather(lat, lng)
        if current:
            # Simulate historical data points
            historical = []
            for i in range(min(days_back, 7)):  # Limit to 7 days for demo
                date = datetime.utcnow() - timedelta(days=i)
                historical.append({
                    'date': date,
                    'temperature': current['temperature'] + (i * 0.5 - 1.5),  # Small variation
                    'humidity': max(20, min(100, current['humidity'] + (i * 2 - 7))),
                    'pressure': current['pressure'] + (i * 0.1 - 0.5),
                    'wind_speed': max(0, current['wind_speed'] + (i * 0.2 - 0.7)),
                    'description': current['description'],
                    'rain': 0,  # Would be actual data in production
                })
            return historical
        return None
    
    def calculate_growing_degree_days(self, temp_data: List[Dict], base_temp: float = 10.0) -> float:
        """
        Calculate Growing Degree Days (GDD) for crop development analysis
        
        Args:
            temp_data: List of temperature data points
            base_temp: Base temperature for calculation (default 10°C)
            
        Returns:
            Total Growing Degree Days
        """
        gdd_total = 0
        for data in temp_data:
            if 'temp_min' in data and 'temp_max' in data:
                avg_temp = (data['temp_min'] + data['temp_max']) / 2
            else:
                avg_temp = data.get('temperature', base_temp)
            
            gdd = max(0, avg_temp - base_temp)
            gdd_total += gdd
            
        return gdd_total
    
    def analyze_weather_conditions(self, current: Dict, forecast: List[Dict]) -> Dict:
        """
        Analyze weather conditions for agricultural insights
        
        Args:
            current: Current weather data
            forecast: Weather forecast data
            
        Returns:
            Weather analysis results
        """
        if not current or not forecast:
            return {}
        
        # Analyze precipitation patterns
        total_rain = sum(f.get('rain', 0) for f in forecast)
        rain_days = len([f for f in forecast if f.get('rain', 0) > 0.1])
        
        # Temperature analysis
        avg_temp = sum(f['temperature'] for f in forecast) / len(forecast)
        temp_range = max(f['temperature'] for f in forecast) - min(f['temperature'] for f in forecast)
        
        # Humidity analysis
        avg_humidity = sum(f['humidity'] for f in forecast) / len(forecast)
        
        # Wind analysis
        avg_wind = sum(f['wind_speed'] for f in forecast) / len(forecast)
        
        return {
            'current_conditions': {
                'temperature': current['temperature'],
                'humidity': current['humidity'],
                'description': current['description'],
                'wind_speed': current['wind_speed']
            },
            'forecast_summary': {
                'avg_temperature': round(avg_temp, 1),
                'temperature_range': round(temp_range, 1),
                'avg_humidity': round(avg_humidity, 1),
                'avg_wind_speed': round(avg_wind, 1),
                'total_precipitation': round(total_rain, 1),
                'rainy_days': rain_days
            },
            'growing_conditions': self._assess_growing_conditions(current, forecast),
            'alerts': self._generate_weather_alerts(current, forecast)
        }
    
    def _assess_growing_conditions(self, current: Dict, forecast: List[Dict]) -> Dict:
        """Assess growing conditions based on weather data"""
        avg_temp = sum(f['temperature'] for f in forecast) / len(forecast)
        avg_humidity = sum(f['humidity'] for f in forecast) / len(forecast)
        total_rain = sum(f.get('rain', 0) for f in forecast)
        
        # Temperature assessment
        if 15 <= avg_temp <= 25:
            temp_rating = "optimal"
        elif 10 <= avg_temp <= 30:
            temp_rating = "good"
        else:
            temp_rating = "suboptimal"
        
        # Humidity assessment
        if 40 <= avg_humidity <= 60:
            humidity_rating = "optimal"
        elif 30 <= avg_humidity <= 70:
            humidity_rating = "good"
        else:
            humidity_rating = "suboptimal"
        
        # Precipitation assessment
        if 10 <= total_rain <= 25:
            rain_rating = "optimal"
        elif 5 <= total_rain <= 35:
            rain_rating = "good"
        else:
            rain_rating = "suboptimal"
        
        return {
            'temperature_rating': temp_rating,
            'humidity_rating': humidity_rating,
            'precipitation_rating': rain_rating,
            'overall_rating': self._calculate_overall_rating([temp_rating, humidity_rating, rain_rating])
        }
    
    def _calculate_overall_rating(self, ratings: List[str]) -> str:
        """Calculate overall growing conditions rating"""
        if all(r == "optimal" for r in ratings):
            return "excellent"
        elif all(r in ["optimal", "good"] for r in ratings):
            return "good"
        elif any(r == "optimal" for r in ratings):
            return "fair"
        else:
            return "poor"
    
    def _generate_weather_alerts(self, current: Dict, forecast: List[Dict]) -> List[str]:
        """Generate weather-based alerts for farmers"""
        alerts = []
        
        # Temperature alerts
        for f in forecast[:3]:  # Check next 3 days
            if f['temperature'] < 5:
                alerts.append("Frost warning: Protect sensitive crops")
                break
            elif f['temperature'] > 35:
                alerts.append("Heat stress warning: Increase irrigation")
                break
        
        # Precipitation alerts
        total_rain = sum(f.get('rain', 0) for f in forecast[:3])
        if total_rain > 50:
            alerts.append("Heavy rain expected: Ensure proper drainage")
        elif total_rain < 2:
            alerts.append("Low precipitation: Monitor soil moisture")
        
        # Wind alerts
        high_wind_days = [f for f in forecast[:3] if f['wind_speed'] > 15]
        if high_wind_days:
            alerts.append("High wind conditions: Secure equipment and check crop support")
        
        # Humidity alerts
        high_humidity_days = [f for f in forecast[:3] if f['humidity'] > 85]
        if len(high_humidity_days) >= 2:
            alerts.append("High humidity conditions: Monitor for fungal diseases")
        
        return alerts