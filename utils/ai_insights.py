"""
AI-powered agricultural insights and recommendations system
Analyzes field data, weather patterns, and satellite imagery to provide actionable farming guidance
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import openai
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class AgricultureAI:
    """Advanced AI system for agricultural analysis and recommendations"""
    
    def __init__(self):
        self.model = "gpt-4o"  # Latest OpenAI model for agricultural analysis
        
    def analyze_field_health(self, field_data: Dict, analysis_data: Dict) -> Dict:
        """
        Analyze overall field health and provide comprehensive insights
        
        Args:
            field_data: Field information (name, area, coordinates)
            analysis_data: NDVI analysis results and health scores
            
        Returns:
            Dictionary with AI analysis and recommendations
        """
        try:
            # Prepare field context for AI analysis
            context = self._prepare_field_context(field_data, analysis_data)
            
            prompt = f"""
            As an expert agricultural consultant with decades of experience in precision farming, 
            analyze this field data and provide comprehensive insights:

            {context}

            Provide a detailed analysis in JSON format with these sections:
            1. "overall_health_assessment": Brief summary of field condition (2-3 sentences)
            2. "critical_insights": Array of 3-5 key findings about the field
            3. "immediate_actions": Array of 3-4 urgent actions needed within 1-2 weeks
            4. "seasonal_recommendations": Array of 3-4 strategic actions for the growing season
            5. "yield_prediction": Expected yield impact based on current conditions
            6. "risk_factors": Array of 2-3 potential risks to monitor
            7. "optimization_opportunities": Array of 2-3 ways to improve field performance

            Focus on practical, actionable advice that farmers can implement immediately.
            Consider soil health, irrigation needs, pest management, and harvest timing.
            """

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert agricultural consultant specializing in precision farming and crop optimization."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            if content:
                ai_analysis = json.loads(content)
            else:
                raise Exception("Empty response from AI model")
            
            return {
                "analysis_date": datetime.now().isoformat(),
                "field_id": field_data.get("id"),
                "field_name": field_data.get("name"),
                "ai_insights": ai_analysis,
                "confidence_score": self._calculate_confidence_score(analysis_data),
                "data_quality": self._assess_data_quality(analysis_data)
            }
            
        except Exception as e:
            return {
                "error": f"AI analysis failed: {str(e)}",
                "fallback_recommendations": self._get_fallback_recommendations()
            }
    
    def generate_zone_specific_insights(self, zone_data: Dict, weather_data: Optional[Dict] = None) -> Dict:
        """
        Generate specific recommendations for individual field zones
        
        Args:
            zone_data: NDVI and health data for specific zones
            weather_data: Current and forecast weather information
            
        Returns:
            Zone-specific AI recommendations
        """
        try:
            weather_context = ""
            if weather_data:
                weather_context = f"""
                Current Weather Conditions:
                - Temperature: {weather_data.get('temperature', 'N/A')}°F
                - Humidity: {weather_data.get('humidity', 'N/A')}%
                - Recent rainfall: {weather_data.get('rainfall', 'N/A')} inches
                - Wind speed: {weather_data.get('wind_speed', 'N/A')} mph
                """

            prompt = f"""
            Analyze these field zones and provide targeted recommendations:

            Zone Analysis Data:
            {json.dumps(zone_data, indent=2)}

            {weather_context}

            For each zone with concerning NDVI values (below 0.6), provide specific recommendations in JSON format:
            {{
                "zone_recommendations": {{
                    "zone_id": {{
                        "issue_diagnosis": "Brief description of the problem",
                        "urgency_level": "High/Medium/Low",
                        "recommended_actions": ["action1", "action2", "action3"],
                        "timeline": "When to implement (e.g., 'Within 3 days', 'Next week')",
                        "expected_outcome": "What improvement to expect"
                    }}
                }},
                "field_wide_patterns": ["pattern1", "pattern2"],
                "irrigation_strategy": "Detailed irrigation recommendations",
                "monitoring_priorities": ["priority1", "priority2"]
            }}

            Focus on practical solutions like irrigation adjustments, nutrient management, and pest control.
            """

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precision agriculture specialist focused on zone-specific field management."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            if content:
                return json.loads(content)
            else:
                return {"error": "Empty response from AI model"}
            
        except Exception as e:
            return {"error": f"Zone analysis failed: {str(e)}"}
    
    def predict_optimal_timing(self, field_data: Dict, crop_type: str = "general") -> Dict:
        """
        Predict optimal timing for various farming activities
        
        Args:
            field_data: Field information and current conditions
            crop_type: Type of crop being grown
            
        Returns:
            Timing recommendations for farming activities
        """
        try:
            current_month = datetime.now().month
            location_context = f"Field location: {field_data.get('center_lat', 'Unknown')}, {field_data.get('center_lng', 'Unknown')}"
            
            prompt = f"""
            Based on the current date ({datetime.now().strftime('%B %d, %Y')}) and field conditions, 
            provide optimal timing recommendations for farming activities:

            {location_context}
            Crop type: {crop_type}
            Field size: {field_data.get('area_acres', 'Unknown')} acres

            Provide recommendations in JSON format:
            {{
                "next_30_days": {{
                    "priority_tasks": ["task1", "task2", "task3"],
                    "optimal_dates": {{
                        "irrigation_check": "specific date or date range",
                        "soil_testing": "specific date or date range",
                        "pest_monitoring": "specific date or date range"
                    }}
                }},
                "seasonal_calendar": {{
                    "spring_activities": ["activity1", "activity2"],
                    "summer_activities": ["activity1", "activity2"],
                    "fall_activities": ["activity1", "activity2"],
                    "winter_activities": ["activity1", "activity2"]
                }},
                "weather_dependent_tasks": ["task1", "task2"],
                "equipment_maintenance": ["check1", "check2"]
            }}

            Consider typical growing seasons for this geographic location and current field health.
            """

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an agricultural timing specialist with expertise in crop calendars and seasonal planning."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1200
            )
            
            content = response.choices[0].message.content
            if content:
                return json.loads(content)
            else:
                return {"error": "Empty response from AI model"}
            
        except Exception as e:
            return {"error": f"Timing prediction failed: {str(e)}"}
    
    def generate_portfolio_insights(self, all_fields_data: List[Dict]) -> Dict:
        """
        Analyze multiple fields to provide portfolio-level insights
        
        Args:
            all_fields_data: List of all field data with analyses
            
        Returns:
            Portfolio-level recommendations and insights
        """
        try:
            # Summarize portfolio data
            total_fields = len(all_fields_data)
            total_area = sum(field.get('area_acres', 0) for field in all_fields_data)
            
            # Calculate portfolio health metrics
            health_scores = []
            for field in all_fields_data:
                if field.get('latest_analysis'):
                    avg_ndvi = field['latest_analysis'].get('field_stats', {}).get('mean_ndvi', 0)
                    health_scores.append(avg_ndvi)
            
            avg_portfolio_health = sum(health_scores) / len(health_scores) if health_scores else 0
            
            portfolio_summary = f"""
            Portfolio Overview:
            - Total fields: {total_fields}
            - Total area: {total_area:.1f} acres
            - Average field health (NDVI): {avg_portfolio_health:.2f}
            - Fields analyzed: {len(health_scores)}
            
            Individual Field Status:
            {json.dumps([{
                'name': field.get('name'),
                'area': field.get('area_acres'),
                'last_analysis': field.get('last_analyzed'),
                'health_status': 'Good' if field.get('latest_analysis', {}).get('field_stats', {}).get('mean_ndvi', 0) > 0.6 else 'Needs Attention'
            } for field in all_fields_data], indent=2)}
            """

            prompt = f"""
            Analyze this agricultural portfolio and provide strategic insights:

            {portfolio_summary}

            Provide comprehensive analysis in JSON format:
            {{
                "portfolio_health_summary": "Overall assessment of all fields",
                "top_performing_fields": ["field names with reasons"],
                "fields_needing_attention": ["field names with specific issues"],
                "resource_allocation_strategy": "How to prioritize time and resources",
                "seasonal_planning": {{
                    "immediate_priorities": ["priority1", "priority2"],
                    "medium_term_goals": ["goal1", "goal2"],
                    "long_term_strategy": ["strategy1", "strategy2"]
                }},
                "efficiency_opportunities": ["opportunity1", "opportunity2"],
                "risk_management": ["risk1", "risk2"],
                "investment_recommendations": ["recommendation1", "recommendation2"]
            }}

            Focus on practical farm management strategies and operational efficiency.
            """

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a farm management consultant specializing in multi-field operations and agricultural portfolio optimization."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            return {"error": f"Portfolio analysis failed: {str(e)}"}
    
    def _prepare_field_context(self, field_data: Dict, analysis_data: Dict) -> str:
        """Prepare comprehensive context for AI analysis"""
        field_stats = analysis_data.get('field_stats', {})
        zone_stats = analysis_data.get('zone_stats', {})
        
        context = f"""
        Field Information:
        - Name: {field_data.get('name', 'Unknown')}
        - Area: {field_data.get('area_acres', 0):.1f} acres
        - Last Analysis: {field_data.get('last_analyzed', 'Never')}
        
        Current Health Metrics:
        - Average NDVI: {field_stats.get('mean_ndvi', 0):.3f}
        - NDVI Range: {field_stats.get('min_ndvi', 0):.3f} to {field_stats.get('max_ndvi', 0):.3f}
        - Field Uniformity (Std Dev): {field_stats.get('std_ndvi', 0):.3f}
        - Healthy Area: {field_stats.get('healthy_percentage', 0):.1f}%
        
        Zone Analysis:
        {json.dumps(zone_stats, indent=2)}
        
        Health Distribution:
        - Excellent (>0.8): {analysis_data.get('health_distribution', {}).get('excellent', 0)}%
        - Good (0.6-0.8): {analysis_data.get('health_distribution', {}).get('good', 0)}%
        - Moderate (0.4-0.6): {analysis_data.get('health_distribution', {}).get('moderate', 0)}%
        - Poor (<0.4): {analysis_data.get('health_distribution', {}).get('poor', 0)}%
        """
        
        return context
    
    def _calculate_confidence_score(self, analysis_data: Dict) -> float:
        """Calculate confidence score based on data quality"""
        score = 0.5  # Base score
        
        # Check data completeness
        if analysis_data.get('field_stats', {}).get('mean_ndvi'):
            score += 0.2
        if analysis_data.get('zone_stats'):
            score += 0.2
        if analysis_data.get('health_distribution'):
            score += 0.1
        
        return min(score, 1.0)
    
    def _assess_data_quality(self, analysis_data: Dict) -> str:
        """Assess the quality of input data"""
        if not analysis_data:
            return "Poor - No analysis data available"
        
        confidence = self._calculate_confidence_score(analysis_data)
        
        if confidence >= 0.8:
            return "Excellent - Comprehensive data available"
        elif confidence >= 0.6:
            return "Good - Sufficient data for analysis"
        elif confidence >= 0.4:
            return "Fair - Limited data, recommendations may be general"
        else:
            return "Poor - Insufficient data for detailed analysis"
    
    def _get_fallback_recommendations(self) -> List[str]:
        """Provide basic recommendations when AI analysis fails"""
        return [
            "Monitor field conditions regularly using satellite imagery",
            "Conduct soil testing to assess nutrient levels",
            "Check irrigation systems for proper coverage",
            "Scout for pests and diseases weekly during growing season",
            "Review weather forecasts for optimal timing of field activities"
        ]

# Helper function for easy integration
def get_ai_insights(field_data: Dict, analysis_data: Dict) -> Dict:
    """
    Quick function to get AI insights for a field
    
    Args:
        field_data: Field information
        analysis_data: NDVI analysis results
        
    Returns:
        AI-generated insights and recommendations
    """
    ai = AgricultureAI()
    return ai.analyze_field_health(field_data, analysis_data)

def get_portfolio_insights(all_fields_data: List[Dict]) -> Dict:
    """
    Quick function to get portfolio-level insights
    
    Args:
        all_fields_data: List of all field data
        
    Returns:
        Portfolio-level AI insights
    """
    ai = AgricultureAI()
    return ai.generate_portfolio_insights(all_fields_data)