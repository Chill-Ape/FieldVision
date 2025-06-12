"""
Automated field monitoring system with email alerts
Monitors vegetation indices for significant changes and sends notifications
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from app import app, db
from models import Field, FieldAnalysis
from ndvi_fetcher import NDVIFetcher
from auth import SentinelHubAuth
from routes import generate_field_ai_insights

# Configure logging
logging.basicConfig(level=logging.INFO)

class FieldMonitor:
    """Automated field monitoring and alert system"""
    
    def __init__(self):
        self.auth_handler = SentinelHubAuth()
        self.ndvi_fetcher = NDVIFetcher(self.auth_handler)
        self.vegetation_indices = ['ndvi', 'ndre', 'moisture', 'evi', 'ndwi', 'chlorophyll']
        
    def should_analyze_field(self, field: Field) -> bool:
        """Determine if field needs analysis based on last update time"""
        if not field.last_analyzed:
            return True
            
        # Check if it's been more than 24 hours since last analysis
        time_since_analysis = datetime.utcnow() - field.last_analyzed
        return time_since_analysis > timedelta(hours=24)
    
    def analyze_field_changes(self, field: Field) -> Dict:
        """Analyze field for vegetation changes and generate insights"""
        logging.info(f"Analyzing field {field.id} - {field.name} for automated monitoring")
        
        try:
            # Get field coordinates and bbox
            coordinates = field.get_polygon_coordinates()
            lats = [coord[0] for coord in coordinates]
            lngs = [coord[1] for coord in coordinates]
            bbox = [min(lngs), min(lats), max(lngs), max(lats)]
            
            # Create geometry for masking
            geometry = {
                "type": "Polygon",
                "coordinates": [[
                    [coord[1], coord[0]] for coord in coordinates
                ] + [[coordinates[0][1], coordinates[0][0]]]]
            }
            
            # Get historical analysis for comparison
            previous_analysis = FieldAnalysis.query.filter_by(field_id=field.id)\
                .order_by(FieldAnalysis.analysis_date.desc()).first()
            
            # Generate current vegetation indices
            current_results = {}
            for index_type in self.vegetation_indices:
                try:
                    image_data = self.ndvi_fetcher.fetch_vegetation_index_image(
                        bbox, index_type, geometry=geometry
                    )
                    if image_data:
                        current_results[index_type] = {'success': True, 'size': len(image_data)}
                        logging.info(f"Successfully generated {index_type.upper()} for field {field.id}")
                    else:
                        current_results[index_type] = {'success': False, 'error': 'Image generation failed'}
                except Exception as e:
                    current_results[index_type] = {'success': False, 'error': str(e)}
            
            # Calculate change metrics
            change_analysis = self.detect_vegetation_changes(field, current_results, previous_analysis)
            
            # Generate AI insights for changes
            analysis_context = {
                "field_name": field.name,
                "field_area_acres": round(field.calculate_area_acres(), 1),
                "total_vegetation_indices": len(self.vegetation_indices),
                "successful_analyses": len([r for r in current_results.values() if r.get('success')]),
                "successful_indices": [idx for idx, r in current_results.items() if r.get('success')],
                "failed_indices": [idx for idx, r in current_results.items() if not r.get('success')],
                "analysis_date": datetime.utcnow().strftime('%Y-%m-%d'),
                "field_coordinates": {
                    "center_lat": field.center_lat,
                    "center_lng": field.center_lng
                },
                "change_analysis": change_analysis,
                "monitoring_context": True
            }
            
            # Get weather data
            try:
                weather_api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
                if weather_api_key:
                    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={field.center_lat}&lon={field.center_lng}&appid={weather_api_key}&units=imperial"
                    weather_response = requests.get(weather_url, timeout=10)
                    if weather_response.status_code == 200:
                        analysis_context['weather'] = weather_response.json()
            except Exception as e:
                logging.warning(f"Failed to fetch weather data: {e}")
            
            ai_insights = generate_field_ai_insights(analysis_context)
            
            # Store new analysis
            new_analysis = FieldAnalysis()
            new_analysis.field_id = field.id
            new_analysis.ai_analysis_data = json.dumps(ai_insights)
            db.session.add(new_analysis)
            field.last_analyzed = datetime.utcnow()
            db.session.commit()
            
            return {
                'field': field,
                'current_results': current_results,
                'change_analysis': change_analysis,
                'ai_insights': ai_insights,
                'urgent_alerts': self.identify_urgent_alerts(change_analysis, ai_insights)
            }
            
        except Exception as e:
            logging.error(f"Error analyzing field {field.id}: {str(e)}")
            return {
                'field': field,
                'error': str(e),
                'urgent_alerts': []
            }
    
    def detect_vegetation_changes(self, field: Field, current_results: Dict, previous_analysis: Optional[FieldAnalysis]) -> Dict:
        """Detect significant changes in vegetation health"""
        if not previous_analysis:
            return {
                'status': 'baseline',
                'message': 'First analysis - establishing baseline',
                'significant_changes': False
            }
        
        # Calculate success rate changes
        current_success_rate = len([r for r in current_results.values() if r.get('success')]) / len(current_results)
        
        # Simple change detection based on successful index generation
        # In a real implementation, you'd compare actual index values
        if current_success_rate < 0.5:
            return {
                'status': 'degraded',
                'message': f'Data quality degraded - only {current_success_rate:.0%} of indices generated successfully',
                'significant_changes': True,
                'severity': 'high'
            }
        elif current_success_rate < 0.8:
            return {
                'status': 'moderate_issues',
                'message': f'Some data issues detected - {current_success_rate:.0%} success rate',
                'significant_changes': True,
                'severity': 'medium'
            }
        else:
            return {
                'status': 'healthy',
                'message': f'All vegetation indices generated successfully ({current_success_rate:.0%})',
                'significant_changes': False
            }
    
    def identify_urgent_alerts(self, change_analysis: Dict, ai_insights: Dict) -> List[Dict]:
        """Identify urgent conditions requiring immediate farmer attention"""
        alerts = []
        
        # Check for significant vegetation changes
        if change_analysis.get('significant_changes') and change_analysis.get('severity') == 'high':
            alerts.append({
                'type': 'vegetation_degradation',
                'priority': 'high',
                'message': 'Significant vegetation health degradation detected',
                'details': change_analysis.get('message', '')
            })
        
        # Check AI insights for critical conditions
        if ai_insights.get('overall_health') in ['Poor', 'Critical']:
            alerts.append({
                'type': 'critical_health',
                'priority': 'urgent',
                'message': f"Field health rated as {ai_insights.get('overall_health')}",
                'details': ai_insights.get('insights', '')
            })
        
        # Check for immediate actions with urgent keywords
        immediate_actions = ai_insights.get('immediate_actions', [])
        urgent_keywords = ['immediate', 'urgent', 'critical', 'emergency', 'severe', 'failing']
        
        for action in immediate_actions:
            if any(keyword in action.lower() for keyword in urgent_keywords):
                alerts.append({
                    'type': 'urgent_action',
                    'priority': 'high',
                    'message': 'Urgent field action required',
                    'details': action
                })
        
        return alerts
    
    def send_email_alert(self, field_analysis: Dict, recipient_email: str) -> bool:
        """Send email alert with field analysis results"""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
            if not sendgrid_api_key:
                logging.warning("SendGrid API key not found - cannot send email alerts")
                return False
            
            field = field_analysis['field']
            ai_insights = field_analysis.get('ai_insights', {})
            urgent_alerts = field_analysis.get('urgent_alerts', [])
            
            # Determine email priority and subject
            if urgent_alerts:
                priority_alerts = [a for a in urgent_alerts if a['priority'] in ['urgent', 'high']]
                if priority_alerts:
                    subject = f"🚨 URGENT: Field Alert - {field.name}"
                else:
                    subject = f"⚠️ Field Update - {field.name}"
            else:
                subject = f"📊 Daily Field Report - {field.name}"
            
            # Generate email content
            email_content = self.generate_email_content(field_analysis)
            
            message = Mail(
                from_email='noreply@fieldvision.ai',
                to_emails=recipient_email,
                subject=subject,
                html_content=email_content
            )
            
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)
            
            logging.info(f"Email alert sent successfully for field {field.id} to {recipient_email}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email alert: {str(e)}")
            return False
    
    def generate_email_content(self, field_analysis: Dict) -> str:
        """Generate HTML email content for field analysis"""
        field = field_analysis['field']
        ai_insights = field_analysis.get('ai_insights', {})
        urgent_alerts = field_analysis.get('urgent_alerts', [])
        change_analysis = field_analysis.get('change_analysis', {})
        
        # Determine overall status color
        health = ai_insights.get('overall_health', 'Unknown')
        if health in ['Excellent', 'Good']:
            status_color = '#28a745'  # Green
        elif health == 'Moderate':
            status_color = '#ffc107'  # Yellow
        else:
            status_color = '#dc3545'  # Red
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>FieldVision AI - Field Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #58a6ff, #0969da); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                .field-info {{ background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; color: white; font-weight: bold; background: {status_color}; }}
                .alert-section {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                .urgent-alert {{ background: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; border-radius: 4px; margin: 10px 0; }}
                .recommendations {{ background: #e7f3ff; border: 1px solid #b8daff; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
                .action-item {{ padding: 8px; background: #fff; border-left: 4px solid #ffc107; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🌾 FieldVision AI</h1>
                    <h2>Field Analysis Report</h2>
                    <p>Automated monitoring update for {field.name}</p>
                </div>
                
                <div class="field-info">
                    <h3>Field Information</h3>
                    <p><strong>Field:</strong> {field.name}</p>
                    <p><strong>Area:</strong> {field.calculate_area_acres():.1f} acres</p>
                    <p><strong>Analysis Date:</strong> {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>
                    <p><strong>Overall Health:</strong> <span class="status-badge">{health}</span></p>
                </div>
        """
        
        # Add urgent alerts section if any
        if urgent_alerts:
            html_content += """
                <div class="alert-section">
                    <h3>🚨 Urgent Alerts</h3>
            """
            for alert in urgent_alerts:
                html_content += f"""
                    <div class="urgent-alert">
                        <strong>{alert['message']}</strong><br>
                        {alert['details']}
                    </div>
                """
            html_content += "</div>"
        
        # Add AI insights
        if ai_insights.get('insights'):
            html_content += f"""
                <div class="recommendations">
                    <h3>🧠 AI Analysis</h3>
                    <p>{ai_insights['insights']}</p>
                </div>
            """
        
        # Add immediate actions
        if ai_insights.get('immediate_actions'):
            html_content += """
                <div class="recommendations">
                    <h3>⚡ Immediate Actions Required</h3>
            """
            for action in ai_insights['immediate_actions']:
                html_content += f'<div class="action-item">• {action}</div>'
            html_content += "</div>"
        
        # Add weather recommendations
        if ai_insights.get('weather_recommendations'):
            html_content += """
                <div class="recommendations">
                    <h3>🌤️ Weather Considerations</h3>
            """
            for rec in ai_insights['weather_recommendations']:
                html_content += f'<div class="action-item">• {rec}</div>'
            html_content += "</div>"
        
        # Add footer
        html_content += f"""
                <div class="footer">
                    <p>This is an automated report from FieldVision AI</p>
                    <p>Field monitoring helps you stay ahead of crop issues and optimize yields</p>
                    <p>Visit your dashboard for detailed vegetation index maps and analysis</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def run_daily_monitoring(self, user_email: str = None) -> Dict:
        """Run daily monitoring for all fields"""
        logging.info("Starting daily field monitoring run")
        
        results = {
            'total_fields': 0,
            'analyzed_fields': 0,
            'urgent_alerts': 0,
            'emails_sent': 0,
            'errors': []
        }
        
        try:
            # Get all fields that need analysis
            fields = Field.query.all()
            results['total_fields'] = len(fields)
            
            for field in fields:
                if self.should_analyze_field(field):
                    try:
                        field_analysis = self.analyze_field_changes(field)
                        results['analyzed_fields'] += 1
                        
                        # Count urgent alerts
                        urgent_alerts = field_analysis.get('urgent_alerts', [])
                        if urgent_alerts:
                            results['urgent_alerts'] += len(urgent_alerts)
                        
                        # Send email if configured and alerts exist
                        if user_email and (urgent_alerts or len(urgent_alerts) == 0):  # Send daily reports
                            if self.send_email_alert(field_analysis, user_email):
                                results['emails_sent'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error analyzing field {field.id}: {str(e)}"
                        logging.error(error_msg)
                        results['errors'].append(error_msg)
            
            logging.info(f"Daily monitoring completed: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in daily monitoring: {str(e)}"
            logging.error(error_msg)
            results['errors'].append(error_msg)
            return results


def run_scheduled_monitoring():
    """Entry point for scheduled monitoring (cron job)"""
    with app.app_context():
        monitor = FieldMonitor()
        
        # You would typically store user email preferences in the database
        # For now, using environment variable
        user_email = os.environ.get('MONITORING_EMAIL')
        
        if user_email:
            results = monitor.run_daily_monitoring(user_email)
            logging.info(f"Scheduled monitoring completed: {results}")
        else:
            logging.info("No monitoring email configured - skipping email alerts")


if __name__ == "__main__":
    run_scheduled_monitoring()