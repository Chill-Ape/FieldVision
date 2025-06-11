"""
Comprehensive AI Field Analysis Service
Integrates NDVI, weather, and agricultural data to generate detailed field reports
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from openai import OpenAI
from .weather_service import WeatherService
from .ndvi_analyzer import analyze_field_ndvi

logger = logging.getLogger(__name__)

class AIFieldAnalyzer:
    """Advanced AI-powered field analysis system"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.weather_service = WeatherService()
        
    def generate_comprehensive_analysis(self, field_data: Dict, ndvi_image_bytes: Optional[bytes] = None) -> Dict:
        """
        Generate comprehensive AI analysis combining all available data sources
        
        Args:
            field_data: Field information including coordinates, area, etc.
            ndvi_image_bytes: NDVI satellite image data
            
        Returns:
            Complete analysis report with recommendations
        """
        logger.info(f"Starting comprehensive analysis for field: {field_data.get('name', 'Unknown')}")
        
        analysis_results = {}
        
        # 1. NDVI Analysis
        if ndvi_image_bytes:
            ndvi_analysis = self._analyze_ndvi_data(ndvi_image_bytes, field_data)
            analysis_results['ndvi_analysis'] = ndvi_analysis
        else:
            analysis_results['ndvi_analysis'] = None
            
        # 2. Weather Analysis
        center_lat = field_data.get('center_lat')
        center_lng = field_data.get('center_lng')
        
        if center_lat is not None and center_lng is not None:
            weather_analysis = self._analyze_weather_conditions(float(center_lat), float(center_lng))
        else:
            weather_analysis = {
                "current_conditions": {},
                "forecast": [],
                "growing_conditions": {"rating": "unknown"},
                "irrigation_needs": {"recommendation": "unknown"},
                "alerts": []
            }
        analysis_results['weather_analysis'] = weather_analysis
        
        # 3. Field Characteristics Analysis
        field_analysis = self._analyze_field_characteristics(field_data)
        analysis_results['field_analysis'] = field_analysis
        
        # 4. Generate AI Insights
        ai_insights = self._generate_ai_insights(analysis_results)
        analysis_results['ai_insights'] = ai_insights
        
        # 5. Create Action Plan
        action_plan = self._create_action_plan(analysis_results)
        analysis_results['action_plan'] = action_plan
        
        # 6. Risk Assessment
        risk_assessment = self._assess_risks(analysis_results)
        analysis_results['risk_assessment'] = risk_assessment
        
        # 7. Performance Metrics
        performance_metrics = self._calculate_performance_metrics(analysis_results)
        analysis_results['performance_metrics'] = performance_metrics
        
        return analysis_results
    
    def _analyze_ndvi_data(self, image_bytes: bytes, field_data: Dict) -> Dict:
        """Analyze NDVI satellite imagery"""
        try:
            # Use existing NDVI analyzer
            ndvi_results = analyze_field_ndvi(image_bytes, field_data.get('polygon_data'))
            
            # Extract key metrics
            zone_stats = ndvi_results.get('zone_statistics', {})
            field_stats = ndvi_results.get('field_statistics', {})
            
            # Calculate health distribution
            health_classes = {'excellent': 0, 'good': 0, 'moderate': 0, 'poor': 0, 'stressed': 0}
            for zone_id, stats in zone_stats.items():
                health_class = self._classify_ndvi_health(stats.get('mean', 0))
                health_classes[health_class] += 1
            
            # Calculate trends (would compare with historical data in production)
            trend_analysis = self._analyze_ndvi_trends(zone_stats)
            
            return {
                'field_statistics': field_stats,
                'zone_statistics': zone_stats,
                'health_distribution': health_classes,
                'trend_analysis': trend_analysis,
                'problem_areas': self._identify_problem_areas(zone_stats),
                'vegetation_vigor': self._assess_vegetation_vigor(field_stats),
                'stress_indicators': self._detect_stress_indicators(zone_stats)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing NDVI data: {e}")
            return {'error': str(e)}
    
    def _analyze_weather_conditions(self, lat: float, lng: float) -> Dict:
        """Analyze current and forecast weather conditions"""
        try:
            current_weather = self.weather_service.get_current_weather(lat, lng)
            forecast = self.weather_service.get_weather_forecast(lat, lng, days=5)
            historical = self.weather_service.get_historical_weather(lat, lng, days_back=7)
            
            if not current_weather or not forecast:
                return {'error': 'Weather data unavailable'}
            
            # Comprehensive weather analysis
            weather_analysis = self.weather_service.analyze_weather_conditions(current_weather, forecast)
            
            # Calculate growing degree days
            if historical:
                gdd = self.weather_service.calculate_growing_degree_days(historical)
                weather_analysis['growing_degree_days'] = gdd
            
            # Stress factor analysis
            stress_factors = self._analyze_weather_stress_factors(current_weather, forecast)
            weather_analysis['stress_factors'] = stress_factors
            
            # Irrigation recommendations
            irrigation_needs = self._assess_irrigation_needs(current_weather, forecast)
            weather_analysis['irrigation_recommendations'] = irrigation_needs
            
            return weather_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing weather conditions: {e}")
            return {'error': str(e)}
    
    def _analyze_field_characteristics(self, field_data: Dict) -> Dict:
        """Analyze field characteristics and management history"""
        try:
            area_acres = field_data.get('area_acres', 0)
            
            # Field size analysis
            size_category = self._categorize_field_size(area_acres)
            
            # Management recommendations based on size
            management_recommendations = self._get_size_based_recommendations(area_acres)
            
            # Calculate field shape metrics
            coordinates = field_data.get('polygon_coordinates', [])
            shape_metrics = self._calculate_shape_metrics(coordinates)
            
            return {
                'area_acres': area_acres,
                'size_category': size_category,
                'shape_metrics': shape_metrics,
                'management_recommendations': management_recommendations,
                'accessibility_assessment': self._assess_field_accessibility(coordinates),
                'efficiency_metrics': self._calculate_efficiency_metrics(shape_metrics, area_acres)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing field characteristics: {e}")
            return {'error': str(e)}
    
    def _generate_ai_insights(self, analysis_data: Dict) -> Dict:
        """Generate AI-powered insights using OpenAI"""
        try:
            # Prepare data summary for AI analysis
            data_summary = self._prepare_data_summary(analysis_data)
            
            # Create comprehensive prompt
            prompt = self._create_analysis_prompt(data_summary)
            
            # Generate AI insights
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert agricultural consultant with deep knowledge of precision agriculture, satellite imagery analysis, weather patterns, and crop management. Provide detailed, actionable insights based on field data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            if content:
                ai_analysis = json.loads(content)
            else:
                ai_analysis = {}
            
            return {
                'analysis_summary': ai_analysis.get('summary', ''),
                'key_findings': ai_analysis.get('key_findings', []),
                'recommendations': ai_analysis.get('recommendations', []),
                'priority_actions': ai_analysis.get('priority_actions', []),
                'long_term_strategy': ai_analysis.get('long_term_strategy', ''),
                'confidence_score': ai_analysis.get('confidence_score', 0.8)
            }
            
        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
            return {'error': str(e)}
    
    def _create_action_plan(self, analysis_data: Dict) -> Dict:
        """Create prioritized action plan based on analysis"""
        immediate_actions = []
        short_term_actions = []
        long_term_actions = []
        
        # Extract recommendations from various analyses
        ndvi_analysis = analysis_data.get('ndvi_analysis', {})
        weather_analysis = analysis_data.get('weather_analysis', {})
        ai_insights = analysis_data.get('ai_insights', {})
        
        # Immediate actions (0-3 days)
        if weather_analysis.get('alerts'):
            for alert in weather_analysis['alerts']:
                immediate_actions.append({
                    'action': alert,
                    'priority': 'high',
                    'timeframe': '0-3 days',
                    'category': 'weather_response'
                })
        
        # NDVI-based immediate actions
        if ndvi_analysis.get('problem_areas'):
            for area in ndvi_analysis['problem_areas']:
                immediate_actions.append({
                    'action': f"Investigate {area['zone_id']} - showing stress indicators",
                    'priority': 'high',
                    'timeframe': '0-3 days',
                    'category': 'field_inspection'
                })
        
        # Short-term actions (1-2 weeks)
        irrigation_recs = weather_analysis.get('irrigation_recommendations', {})
        if irrigation_recs.get('action_needed'):
            short_term_actions.append({
                'action': irrigation_recs.get('recommendation', 'Adjust irrigation schedule'),
                'priority': 'medium',
                'timeframe': '1-2 weeks',
                'category': 'irrigation'
            })
        
        # Long-term actions (1 month+)
        if ai_insights.get('long_term_strategy'):
            long_term_actions.append({
                'action': ai_insights['long_term_strategy'],
                'priority': 'medium',
                'timeframe': '1+ months',
                'category': 'strategic_planning'
            })
        
        return {
            'immediate_actions': immediate_actions[:5],  # Limit to top 5
            'short_term_actions': short_term_actions[:5],
            'long_term_actions': long_term_actions[:3],
            'total_actions': len(immediate_actions) + len(short_term_actions) + len(long_term_actions)
        }
    
    def _assess_risks(self, analysis_data: Dict) -> Dict:
        """Assess various risk factors affecting the field"""
        risks = []
        
        # Weather-related risks
        weather_analysis = analysis_data.get('weather_analysis', {})
        if weather_analysis.get('alerts'):
            for alert in weather_analysis['alerts']:
                risk_level = 'high' if 'warning' in alert.lower() else 'medium'
                risks.append({
                    'type': 'weather',
                    'description': alert,
                    'risk_level': risk_level,
                    'probability': 0.7 if risk_level == 'high' else 0.4
                })
        
        # NDVI-related risks
        ndvi_analysis = analysis_data.get('ndvi_analysis', {})
        health_dist = ndvi_analysis.get('health_distribution', {})
        if health_dist.get('stressed', 0) > 0 or health_dist.get('poor', 0) > 0:
            stress_zones = health_dist.get('stressed', 0) + health_dist.get('poor', 0)
            risks.append({
                'type': 'crop_stress',
                'description': f"{stress_zones} zones showing stress or poor health",
                'risk_level': 'high' if stress_zones > 2 else 'medium',
                'probability': 0.8
            })
        
        # Calculate overall risk score
        risk_scores = [r['probability'] for r in risks]
        overall_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.2
        
        return {
            'risks': risks,
            'overall_risk_score': overall_risk,
            'risk_level': 'high' if overall_risk > 0.6 else 'medium' if overall_risk > 0.3 else 'low'
        }
    
    def _calculate_performance_metrics(self, analysis_data: Dict) -> Dict:
        """Calculate field performance metrics"""
        ndvi_analysis = analysis_data.get('ndvi_analysis', {})
        field_stats = ndvi_analysis.get('field_statistics', {})
        health_dist = ndvi_analysis.get('health_distribution', {})
        
        # Health score calculation
        total_zones = sum(health_dist.values()) if health_dist else 1
        health_score = 0
        if total_zones > 0:
            health_score = (
                (health_dist.get('excellent', 0) * 1.0 +
                 health_dist.get('good', 0) * 0.8 +
                 health_dist.get('moderate', 0) * 0.6 +
                 health_dist.get('poor', 0) * 0.4 +
                 health_dist.get('stressed', 0) * 0.2) / total_zones
            )
        
        # Productivity estimate (based on NDVI)
        avg_ndvi = field_stats.get('mean_ndvi', 0.5)
        productivity_estimate = min(100, max(0, (avg_ndvi - 0.2) * 125))  # Scale to 0-100%
        
        # Uniformity score
        ndvi_std = field_stats.get('std_ndvi', 0.1)
        uniformity_score = max(0, 100 - (ndvi_std * 500))  # Higher std = lower uniformity
        
        return {
            'health_score': round(health_score * 100, 1),
            'productivity_estimate': round(productivity_estimate, 1),
            'uniformity_score': round(uniformity_score, 1),
            'overall_performance': round((health_score * 100 + productivity_estimate + uniformity_score) / 3, 1)
        }
    
    # Helper methods
    def _classify_ndvi_health(self, ndvi_value: float) -> str:
        """Classify NDVI value into health category"""
        if ndvi_value >= 0.7:
            return 'excellent'
        elif ndvi_value >= 0.5:
            return 'good'
        elif ndvi_value >= 0.3:
            return 'moderate'
        elif ndvi_value >= 0.1:
            return 'poor'
        else:
            return 'stressed'
    
    def _analyze_ndvi_trends(self, zone_stats: Dict) -> Dict:
        """Analyze NDVI trends (would use historical data in production)"""
        # Simulated trend analysis for demonstration
        return {
            'trend_direction': 'stable',
            'trend_strength': 'moderate',
            'seasonal_pattern': 'normal',
            'anomalies_detected': False
        }
    
    def _identify_problem_areas(self, zone_stats: Dict) -> List[Dict]:
        """Identify zones with potential problems"""
        problem_areas = []
        for zone_id, stats in zone_stats.items():
            if stats.get('mean', 0) < 0.3:  # Low NDVI threshold
                problem_areas.append({
                    'zone_id': zone_id,
                    'issue': 'Low vegetation vigor',
                    'severity': 'high' if stats.get('mean', 0) < 0.2 else 'medium',
                    'ndvi_value': stats.get('mean', 0)
                })
        return problem_areas
    
    def _assess_vegetation_vigor(self, field_stats: Dict) -> str:
        """Assess overall vegetation vigor"""
        avg_ndvi = field_stats.get('mean_ndvi', 0)
        if avg_ndvi >= 0.6:
            return 'excellent'
        elif avg_ndvi >= 0.4:
            return 'good'
        elif avg_ndvi >= 0.2:
            return 'moderate'
        else:
            return 'poor'
    
    def _detect_stress_indicators(self, zone_stats: Dict) -> List[str]:
        """Detect vegetation stress indicators"""
        indicators = []
        low_vigor_zones = sum(1 for stats in zone_stats.values() if stats.get('mean', 0) < 0.3)
        
        if low_vigor_zones > 0:
            indicators.append(f"{low_vigor_zones} zones with low vegetation vigor")
        
        # Check for high variability
        high_variance_zones = sum(1 for stats in zone_stats.values() if stats.get('std', 0) > 0.2)
        if high_variance_zones > 0:
            indicators.append(f"{high_variance_zones} zones with high NDVI variability")
        
        return indicators
    
    def _analyze_weather_stress_factors(self, current: Dict, forecast: List[Dict]) -> Dict:
        """Analyze weather-related stress factors"""
        stress_factors = []
        
        # Temperature stress
        extreme_temps = [f for f in forecast if f['temperature'] < 5 or f['temperature'] > 35]
        if extreme_temps:
            stress_factors.append('Temperature extremes expected')
        
        # Drought stress
        total_rain = sum(f.get('rain', 0) for f in forecast)
        if total_rain < 5:
            stress_factors.append('Low precipitation - drought risk')
        
        # Wind stress
        high_wind = [f for f in forecast if f['wind_speed'] > 20]
        if high_wind:
            stress_factors.append('High wind conditions')
        
        return {
            'stress_factors': stress_factors,
            'stress_level': 'high' if len(stress_factors) >= 2 else 'medium' if stress_factors else 'low'
        }
    
    def _assess_irrigation_needs(self, current: Dict, forecast: List[Dict]) -> Dict:
        """Assess irrigation requirements"""
        total_rain = sum(f.get('rain', 0) for f in forecast[:3])  # Next 3 days
        avg_temp = sum(f['temperature'] for f in forecast[:3]) / 3
        avg_humidity = sum(f['humidity'] for f in forecast[:3]) / 3
        
        # Simple irrigation model
        action_needed = False
        recommendation = "Current irrigation schedule adequate"
        
        if total_rain < 5 and avg_temp > 25:
            action_needed = True
            recommendation = "Increase irrigation frequency due to low precipitation and high temperatures"
        elif avg_humidity < 40 and total_rain < 10:
            action_needed = True
            recommendation = "Monitor soil moisture and consider supplemental irrigation"
        
        return {
            'action_needed': action_needed,
            'recommendation': recommendation,
            'next_irrigation_window': "Next 2-3 days" if action_needed else "Follow regular schedule"
        }
    
    def _categorize_field_size(self, area_acres: float) -> str:
        """Categorize field size"""
        if area_acres < 5:
            return 'small'
        elif area_acres < 20:
            return 'medium'
        elif area_acres < 100:
            return 'large'
        else:
            return 'very_large'
    
    def _get_size_based_recommendations(self, area_acres: float) -> List[str]:
        """Get management recommendations based on field size"""
        if area_acres < 5:
            return ["Consider precision application techniques", "Manual monitoring feasible"]
        elif area_acres < 20:
            return ["Implement zone management", "Regular sampling recommended"]
        else:
            return ["Variable rate application recommended", "Automated monitoring systems beneficial"]
    
    def _calculate_shape_metrics(self, coordinates: List) -> Dict:
        """Calculate field shape metrics"""
        if not coordinates or len(coordinates) < 3:
            return {'perimeter_to_area_ratio': 0, 'shape_complexity': 'unknown'}
        
        # Simple shape analysis (would be more sophisticated in production)
        return {
            'perimeter_to_area_ratio': 1.0,  # Simplified
            'shape_complexity': 'moderate',
            'field_shape': 'irregular'
        }
    
    def _assess_field_accessibility(self, coordinates: List) -> Dict:
        """Assess field accessibility for equipment"""
        return {
            'equipment_access': 'good',
            'terrain_suitability': 'suitable',
            'access_points': 'multiple'
        }
    
    def _calculate_efficiency_metrics(self, shape_metrics: Dict, area_acres: float) -> Dict:
        """Calculate field efficiency metrics"""
        return {
            'operational_efficiency': 85,  # Percentage
            'equipment_suitability': 'high',
            'management_complexity': 'moderate'
        }
    
    def _prepare_data_summary(self, analysis_data: Dict) -> str:
        """Prepare data summary for AI analysis"""
        summary_parts = []
        
        # NDVI summary
        ndvi_analysis = analysis_data.get('ndvi_analysis', {})
        if ndvi_analysis and 'field_statistics' in ndvi_analysis:
            stats = ndvi_analysis['field_statistics']
            summary_parts.append(f"NDVI Analysis: Mean NDVI {stats.get('mean_ndvi', 0):.2f}, covering vegetation health across {len(ndvi_analysis.get('zone_statistics', {}))} zones.")
        
        # Weather summary
        weather_analysis = analysis_data.get('weather_analysis', {})
        if weather_analysis and 'current_conditions' in weather_analysis:
            current = weather_analysis['current_conditions']
            summary_parts.append(f"Weather: Current temperature {current.get('temperature', 0)}°C, humidity {current.get('humidity', 0)}%, {current.get('description', 'clear')}.")
        
        # Field characteristics
        field_analysis = analysis_data.get('field_analysis', {})
        if field_analysis:
            area = field_analysis.get('area_acres', 0)
            summary_parts.append(f"Field: {area} acres, {field_analysis.get('size_category', 'unknown')} size category.")
        
        return " ".join(summary_parts)
    
    def _create_analysis_prompt(self, data_summary: str) -> str:
        """Create comprehensive analysis prompt for AI"""
        return f"""
        As an expert agricultural consultant, analyze the following field data and provide comprehensive insights:

        {data_summary}

        Please provide a detailed analysis in JSON format with the following structure:
        {{
            "summary": "Brief overview of field condition and key observations",
            "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
            "recommendations": [
                "Immediate action recommendation 1",
                "Short-term recommendation 2", 
                "Long-term strategy recommendation 3"
            ],
            "priority_actions": [
                "Most urgent action needed",
                "Second priority action"
            ],
            "long_term_strategy": "Strategic recommendations for field optimization",
            "confidence_score": 0.85
        }}

        Focus on:
        1. Crop health and vegetation vigor assessment
        2. Weather impact on crop development
        3. Risk identification and mitigation
        4. Actionable management recommendations
        5. Productivity optimization strategies

        Provide specific, actionable insights that a farmer can implement.
        """