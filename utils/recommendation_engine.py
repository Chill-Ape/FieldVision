"""
FieldVision AI Recommendation Engine
Provides intelligent agricultural recommendations based on NDVI and weather data
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FieldRecommendationEngine:
    """
    AI-powered recommendation system for agricultural decision making
    Phase 1: Rule-based logic (expandable to ML in future)
    """
    
    def __init__(self):
        """Initialize the recommendation engine with crop-specific parameters"""
        self.crop_parameters = {
            'grapevine': {
                'optimal_ndvi_range': (0.5, 0.8),
                'critical_ndvi_threshold': 0.3,
                'water_stress_threshold': 10,  # mm/week
                'heat_stress_threshold': 35,   # °C
                'optimal_humidity_range': (60, 80)
            },
            'corn': {
                'optimal_ndvi_range': (0.6, 0.9),
                'critical_ndvi_threshold': 0.4,
                'water_stress_threshold': 15,
                'heat_stress_threshold': 32,
                'optimal_humidity_range': (65, 85)
            },
            'wheat': {
                'optimal_ndvi_range': (0.4, 0.7),
                'critical_ndvi_threshold': 0.25,
                'water_stress_threshold': 12,
                'heat_stress_threshold': 30,
                'optimal_humidity_range': (55, 75)
            }
        }
    
    def generate_field_recommendations(self, 
                                     ndvi_zones: Dict[str, float], 
                                     weather_data: Dict, 
                                     crop_type: str = 'grapevine') -> Dict:
        """
        Generate comprehensive recommendations for an entire field
        
        Args:
            ndvi_zones: Dictionary with zone IDs and NDVI values
            weather_data: Weather data from weather service
            crop_type: Type of crop being analyzed
            
        Returns:
            Dictionary with field-wide and zone-specific recommendations
        """
        try:
            # Get crop parameters
            crop_params = self.crop_parameters.get(crop_type, self.crop_parameters['grapevine'])
            
            # Extract weather metrics
            weather_summary = weather_data.get('agricultural_summary', {})
            rainfall_7d = weather_summary.get('total_rainfall_7d', 0)
            avg_temp_7d = weather_summary.get('avg_temperature_7d', 20)
            current_weather = weather_data.get('current', {})
            
            # Analyze overall field health
            avg_ndvi = sum(ndvi_zones.values()) / len(ndvi_zones) if ndvi_zones else 0
            field_health = self._classify_field_health(avg_ndvi, crop_params)
            
            # Generate field-wide recommendations
            field_recommendations = self._generate_field_wide_recommendations(
                avg_ndvi, rainfall_7d, avg_temp_7d, crop_params, weather_summary
            )
            
            # Generate zone-specific recommendations
            zone_recommendations = {}
            for zone_id, ndvi_value in ndvi_zones.items():
                zone_recommendations[zone_id] = self._generate_zone_recommendations(
                    zone_id, ndvi_value, rainfall_7d, avg_temp_7d, crop_params
                )
            
            # Calculate priority actions
            priority_actions = self._identify_priority_actions(
                ndvi_zones, weather_summary, crop_params
            )
            
            return {
                'field_health': field_health,
                'average_ndvi': round(avg_ndvi, 3),
                'weather_context': self._format_weather_context(weather_data),
                'field_recommendations': field_recommendations,
                'zone_recommendations': zone_recommendations,
                'priority_actions': priority_actions,
                'crop_type': crop_type,
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return self._generate_fallback_recommendations(ndvi_zones, crop_type)
    
    def _classify_field_health(self, avg_ndvi: float, crop_params: Dict) -> Dict:
        """Classify overall field health status"""
        optimal_min, optimal_max = crop_params['optimal_ndvi_range']
        critical_threshold = crop_params['critical_ndvi_threshold']
        
        if avg_ndvi >= optimal_min and avg_ndvi <= optimal_max:
            status = "excellent"
            description = "Vegetation is thriving with optimal photosynthetic activity"
            icon = "🌿"
        elif avg_ndvi >= critical_threshold:
            status = "good" if avg_ndvi >= (optimal_min * 0.8) else "fair"
            description = "Vegetation shows healthy growth with room for improvement"
            icon = "🌱"
        else:
            status = "poor"
            description = "Vegetation stress detected - immediate attention required"
            icon = "⚠️"
        
        return {
            'status': status,
            'description': description,
            'icon': icon,
            'score': min(100, max(0, int((avg_ndvi / optimal_max) * 100)))
        }
    
    def _generate_field_wide_recommendations(self, avg_ndvi: float, rainfall_7d: float, 
                                           avg_temp_7d: float, crop_params: Dict,
                                           weather_summary: Dict) -> List[Dict]:
        """Generate field-wide management recommendations"""
        recommendations = []
        
        # Water management recommendations
        if rainfall_7d < crop_params['water_stress_threshold']:
            if avg_ndvi < crop_params['critical_ndvi_threshold']:
                recommendations.append({
                    'category': 'irrigation',
                    'priority': 'high',
                    'title': 'Immediate Irrigation Required',
                    'description': f'Low NDVI ({avg_ndvi:.2f}) combined with insufficient rainfall ({rainfall_7d}mm) indicates severe water stress.',
                    'action': 'Begin deep irrigation immediately. Apply 25-30mm water per session.',
                    'icon': '💧'
                })
            else:
                recommendations.append({
                    'category': 'irrigation',
                    'priority': 'medium',
                    'title': 'Increase Irrigation Schedule',
                    'description': f'Below-average rainfall ({rainfall_7d}mm in 7 days) may impact plant health.',
                    'action': 'Increase irrigation frequency by 20-30%. Monitor soil moisture daily.',
                    'icon': '🚿'
                })
        
        # Temperature stress management
        if weather_summary.get('heat_stress') == 'high':
            recommendations.append({
                'category': 'climate',
                'priority': 'high',
                'title': 'Heat Stress Mitigation',
                'description': f'High temperatures ({avg_temp_7d:.1f}°C average) causing plant stress.',
                'action': 'Apply shade cloth, increase irrigation timing to early morning/evening.',
                'icon': '🌡️'
            })
        
        # Fertilization recommendations based on NDVI
        optimal_min, optimal_max = crop_params['optimal_ndvi_range']
        if avg_ndvi < optimal_min * 0.9:
            recommendations.append({
                'category': 'nutrition',
                'priority': 'medium',
                'title': 'Nutrient Assessment Recommended',
                'description': f'NDVI below optimal range suggests possible nutrient deficiency.',
                'action': 'Conduct soil test for N-P-K levels. Consider foliar feeding with balanced fertilizer.',
                'icon': '🧪'
            })
        
        # Pest and disease monitoring
        if avg_ndvi < crop_params['critical_ndvi_threshold'] and rainfall_7d > 20:
            recommendations.append({
                'category': 'protection',
                'priority': 'medium',
                'title': 'Enhanced Monitoring Required',
                'description': 'Low NDVI with high rainfall may indicate pest or disease pressure.',
                'action': 'Increase field scouting frequency. Check for signs of fungal diseases.',
                'icon': '🔍'
            })
        
        return recommendations
    
    def _generate_zone_recommendations(self, zone_id: str, ndvi_value: float, 
                                     rainfall_7d: float, avg_temp_7d: float,
                                     crop_params: Dict) -> Dict:
        """Generate recommendations for individual field zones"""
        optimal_min, optimal_max = crop_params['optimal_ndvi_range']
        critical_threshold = crop_params['critical_ndvi_threshold']
        
        # Zone health classification
        if ndvi_value >= optimal_min:
            health_status = "healthy"
            priority = "low"
        elif ndvi_value >= critical_threshold:
            health_status = "moderate_stress"
            priority = "medium"
        else:
            health_status = "severe_stress"
            priority = "high"
        
        # Generate specific recommendations
        recommendations = []
        
        if health_status == "severe_stress":
            if rainfall_7d < crop_params['water_stress_threshold']:
                recommendations.append("Immediate targeted irrigation - apply 30-40mm")
                recommendations.append("Soil moisture assessment within 24 hours")
            else:
                recommendations.append("Investigate root zone issues - check for pests/diseases")
                recommendations.append("Consider soil compaction or drainage problems")
        
        elif health_status == "moderate_stress":
            recommendations.append("Increase monitoring frequency to daily")
            recommendations.append("Adjust irrigation schedule - add 15-20mm weekly")
            
        else:  # healthy
            recommendations.append("Maintain current management practices")
            recommendations.append("Continue regular monitoring schedule")
        
        return {
            'health_status': health_status,
            'priority': priority,
            'ndvi_value': round(ndvi_value, 3),
            'recommendations': recommendations,
            'zone_name': self._get_zone_name(zone_id)
        }
    
    def _identify_priority_actions(self, ndvi_zones: Dict, weather_summary: Dict, 
                                 crop_params: Dict) -> List[Dict]:
        """Identify immediate priority actions across the field"""
        priority_actions = []
        
        # Count zones in distress
        critical_zones = [zone for zone, ndvi in ndvi_zones.items() 
                         if ndvi < crop_params['critical_ndvi_threshold']]
        
        if len(critical_zones) > len(ndvi_zones) * 0.3:  # More than 30% of zones critical
            priority_actions.append({
                'urgency': 'immediate',
                'action': 'Field-wide intervention required',
                'details': f'{len(critical_zones)} zones showing critical NDVI levels',
                'deadline': '24 hours'
            })
        
        # Weather-based priorities
        if weather_summary.get('drought_risk') == 'high':
            priority_actions.append({
                'urgency': 'high',
                'action': 'Implement drought management protocol',
                'details': 'Severe water stress conditions detected',
                'deadline': '48 hours'
            })
        
        return priority_actions
    
    def _format_weather_context(self, weather_data: Dict) -> Dict:
        """Format weather data for display"""
        current = weather_data.get('current', {})
        summary = weather_data.get('agricultural_summary', {})
        
        return {
            'current_conditions': {
                'temperature': f"{current.get('temperature', 0):.1f}°C",
                'humidity': f"{current.get('humidity', 0)}%",
                'description': current.get('description', 'unknown').title()
            },
            'week_summary': {
                'total_rainfall': f"{summary.get('total_rainfall_7d', 0)}mm",
                'avg_temperature': f"{summary.get('avg_temperature_7d', 0):.1f}°C",
                'growing_conditions': summary.get('growing_conditions', 'unknown').title(),
                'drought_risk': summary.get('drought_risk', 'unknown').title()
            }
        }
    
    def _get_zone_name(self, zone_id: str) -> str:
        """Convert zone ID to readable name"""
        zone_names = {
            'zone_0_0': 'Northwest', 'zone_0_1': 'North', 'zone_0_2': 'Northeast',
            'zone_1_0': 'West', 'zone_1_1': 'Center', 'zone_1_2': 'East',
            'zone_2_0': 'Southwest', 'zone_2_1': 'South', 'zone_2_2': 'Southeast'
        }
        return zone_names.get(zone_id, zone_id.replace('_', ' ').title())
    
    def _generate_fallback_recommendations(self, ndvi_zones: Dict, crop_type: str) -> Dict:
        """Generate basic recommendations when full analysis fails"""
        avg_ndvi = sum(ndvi_zones.values()) / len(ndvi_zones) if ndvi_zones else 0
        
        return {
            'field_health': {
                'status': 'unknown',
                'description': 'Limited analysis available',
                'icon': '❓',
                'score': 0
            },
            'average_ndvi': round(avg_ndvi, 3),
            'weather_context': {'note': 'Weather data unavailable'},
            'field_recommendations': [{
                'category': 'general',
                'priority': 'medium',
                'title': 'Continue Standard Monitoring',
                'description': 'Maintain regular field monitoring practices.',
                'action': 'Visual inspection and standard care protocols.',
                'icon': '👁️'
            }],
            'zone_recommendations': {},
            'priority_actions': [],
            'crop_type': crop_type,
            'analysis_timestamp': datetime.utcnow().isoformat()
        }

# Convenience functions for integration
def analyze_field_with_weather(ndvi_zones: Dict, weather_data: Dict, 
                              crop_type: str = 'grapevine') -> Dict:
    """
    Main entry point for field analysis with recommendations
    
    Args:
        ndvi_zones: Dictionary mapping zone IDs to NDVI values
        weather_data: Weather data from weather service
        crop_type: Type of crop (grapevine, corn, wheat)
        
    Returns:
        Complete analysis with recommendations
    """
    engine = FieldRecommendationEngine()
    return engine.generate_field_recommendations(ndvi_zones, weather_data, crop_type)

def get_supported_crops() -> List[str]:
    """Get list of supported crop types"""
    engine = FieldRecommendationEngine()
    return list(engine.crop_parameters.keys())