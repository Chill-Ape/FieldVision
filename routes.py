from flask import render_template, request, jsonify, flash, redirect, url_for, Response, render_template_string
from app import app, db
from models import Field, FieldAnalysis
from utils.sentinel_hub import fetch_ndvi_image
from utils.ndvi_processor import process_ndvi_data, calculate_field_zones
from utils.ai_recommendations import generate_recommendations
from utils.weather_service import WeatherService
from utils.ai_field_analyzer import AIFieldAnalyzer
from auth import SentinelHubAuth
from ndvi_fetcher import NDVIFetcher
import logging
import json
from datetime import datetime

# Initialize satellite functionality
logger = logging.getLogger(__name__)
auth_handler = SentinelHubAuth()
ndvi_fetcher = NDVIFetcher(auth_handler)

def is_ajax_request():
    """Check if the current request is an AJAX request"""
    return request.args.get('ajax') == '1'

def render_spa_template(template_name, **context):
    """Render template for SPA - return only content block for AJAX requests"""
    if is_ajax_request():
        # For AJAX requests, return the full template
        # The JavaScript in base.html will handle extracting the content
        return render_template(template_name, **context)
    else:
        # For regular requests, render full template
        return render_template(template_name, **context)

@app.route('/')
def index():
    """Main page with map interface"""
    return render_template('index_clean.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard showing all saved fields"""
    fields = Field.query.order_by(Field.created_at.desc()).all()
    return render_template('dashboard_content.html', fields=fields)

@app.route('/field/<int:field_id>')
def field_detail(field_id):
    """Detailed view of a specific field"""
    field = Field.query.get_or_404(field_id)
    latest_analysis = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).first()
    return render_template('field_detail.html', field=field, analysis=latest_analysis)

@app.route('/sites')
def sites():
    """Sites management dashboard (alias for dashboard)"""
    fields = Field.query.order_by(Field.created_at.desc()).all()
    return render_template('dashboard.html', fields=fields)

@app.route('/reports')
def reports():
    """Reports dashboard showing all field reports"""
    try:
        # Eagerly load analyses relationships
        from sqlalchemy.orm import joinedload
        fields = Field.query.options(joinedload(Field.analyses)).order_by(Field.created_at.desc()).all()
        logger.info(f"Found {len(fields)} fields for reports page")
        for field in fields:
            logger.info(f"Field: {field.name}, ID: {field.id}, Analyses: {len(field.analyses)}")
        return render_template('reports.html', fields=fields)
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        return render_template('reports.html', fields=[])

@app.route('/site/<int:field_id>')
def site_project(field_id):
    """Individual site project page with comprehensive data and controls"""
    from sqlalchemy.orm import joinedload
    field = Field.query.options(joinedload(Field.analyses)).get_or_404(field_id)
    
    # Sort analyses by date descending (newest first) in Python since template filter isn't working
    field.analyses = sorted(field.analyses, key=lambda x: x.analysis_date, reverse=True)
    
    latest_analysis = field.analyses[0] if field.analyses else None
    
    if is_ajax_request():
        return render_template('site_project.html', field=field, latest_analysis=latest_analysis)
    return render_template('site_project.html', field=field, latest_analysis=latest_analysis)

@app.route('/field/<int:field_id>/report')
def field_report(field_id):
    """Comprehensive field report page"""
    field = Field.query.get_or_404(field_id)
    latest_analysis = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).first()
    return render_template('field_report.html', field=field, analysis=latest_analysis)

@app.route('/api/save_field', methods=['POST'])
def save_field():
    """Save a new field with polygon data"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'polygon' not in data:
            return jsonify({'error': 'Missing required data'}), 400
        
        # Parse polygon data if it's a string
        polygon_data = data['polygon']
        if isinstance(polygon_data, str):
            coordinates = json.loads(polygon_data)
        else:
            coordinates = polygon_data
        
        if not coordinates or len(coordinates) < 3:
            return jsonify({'error': 'Invalid polygon data'}), 400
        
        # Use provided center coordinates or calculate them
        if 'center_lat' in data and 'center_lng' in data:
            center_lat = float(data['center_lat'])
            center_lng = float(data['center_lng'])
        else:
            # Calculate center point - coordinates are [lat, lng]
            center_lat = sum(float(coord[0]) for coord in coordinates) / len(coordinates)
            center_lng = sum(float(coord[1]) for coord in coordinates) / len(coordinates)
        
        # Create new field
        field = Field()
        field.name = data['name']
        field.polygon_data = json.dumps(coordinates)
        field.center_lat = center_lat
        field.center_lng = center_lng
        field.created_at = datetime.utcnow()
        
        db.session.add(field)
        db.session.commit()
        
        # Generate initial NDVI analysis for the new field (REQUIRED)
        from ndvi_fetcher import NDVIFetcher
        from auth import SentinelHubAuth
        from utils.ndvi_analyzer import analyze_field_ndvi
        from utils.ai_recommendations import generate_recommendations, get_zone_ndvi_values
        
        # Initialize NDVI fetcher
        auth_handler = SentinelHubAuth()
        if not auth_handler.is_authenticated():
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Sentinel Hub authentication required. Please configure API credentials.'}), 500
        
        ndvi_fetcher = NDVIFetcher(auth_handler)
        
        # Calculate bounding box from coordinates
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        bbox = [min(lngs), min(lats), max(lngs), max(lats)]
        
        # Create GeoJSON geometry for masking
        geometry = {
            "type": "Polygon",
            "coordinates": [[[coord[1], coord[0]] for coord in coordinates + [coordinates[0]]]]
        }
        
        # Save field first for faster response
        db.session.add(field)
        db.session.commit()
        
        logging.info(f"Field '{field.name}' saved successfully with ID {field.id}")
        
        # Schedule NDVI processing in background (faster user experience)
        try:
            # Quick NDVI fetch for immediate feedback
            ndvi_image_bytes = ndvi_fetcher.fetch_vegetation_index_image(bbox, 'ndvi', geometry=geometry)
            
            if ndvi_image_bytes:
                # Basic validation - just check if we got data
                field.cache_ndvi_image(ndvi_image_bytes)
                field.last_analyzed = datetime.utcnow()
                
                # Quick analysis for basic validation
                analysis_results = analyze_field_ndvi(ndvi_image_bytes, geometry)
                zone_stats = analysis_results.get('zone_statistics', {})
                
                if zone_stats:
                    # Generate basic recommendations
                    zone_ndvi_values = get_zone_ndvi_values(analysis_results)
                    recommendations = generate_recommendations(zone_ndvi_values, analysis_results.get('zones', {}))
                    
                    # Create analysis record
                    analysis = FieldAnalysis()
                    analysis.field_id = field.id
                    analysis.set_ndvi_data(zone_ndvi_values)
                    analysis.set_health_scores(zone_stats)
                    analysis.set_recommendations(recommendations)
                    analysis.analysis_date = datetime.utcnow()
                    
                    db.session.add(analysis)
                
                db.session.commit()
                logging.info(f"Generated initial NDVI analysis for field '{field.name}'")
            else:
                logging.warning(f"NDVI generation failed for field {field.id}, but field was saved")
                
        except Exception as e:
            logging.warning(f"NDVI processing failed for field {field.id}: {e}, but field was saved")
        
        logging.info(f"Field '{field.name}' saved successfully with ID {field.id}")
        return jsonify({'success': True, 'field_id': field.id})
        
    except Exception as e:
        logging.error(f"Error saving field: {str(e)}")
        try:
            logging.error(f"Request data: {data}")
        except:
            logging.error("Request data not available")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to save field: {str(e)}'}), 500

@app.route('/field/<int:field_id>/analyze', methods=['POST'])
def analyze_field_vegetation_index(field_id):
    """Generate vegetation index analysis for a specific field"""
    try:
        field = Field.query.get_or_404(field_id)
        data = request.get_json()
        index_type = data.get('index_type', 'ndvi')
        
        # Get polygon coordinates
        coordinates = field.get_polygon_coordinates()
        
        # Calculate bounding box from coordinates
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        bbox = [min(lngs), min(lats), max(lngs), max(lats)]
        
        # Create GeoJSON geometry for polygon masking
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [coord[1], coord[0]] for coord in coordinates
            ] + [[coordinates[0][1], coordinates[0][0]]]]
        }
        
        logging.info(f"Generating {index_type.upper()} analysis for field {field_id}")
        
        return jsonify({
            'success': True, 
            'bbox': bbox, 
            'geometry': geometry,
            'index_type': index_type
        })
        
    except Exception as e:
        logging.error(f"Error analyzing field {field_id}: {str(e)}")
        return jsonify({'error': f'Failed to analyze field: {str(e)}'}), 500

@app.route('/field/<int:field_id>/ai-analysis', methods=['POST'])
def comprehensive_ai_analysis(field_id):
    """Generate comprehensive AI analysis for all vegetation indices"""
    try:
        field = Field.query.get_or_404(field_id)
        data = request.get_json()
        analysis_results = data.get('analysis_results', {})
        
        # Count successful analyses
        successful_indices = [idx for idx, result in analysis_results.items() if result.get('success')]
        total_indices = len(analysis_results)
        
        # Get field information
        field_area = field.calculate_area_acres()
        coordinates = field.get_polygon_coordinates()
        
        # Get weather data for the field location
        weather_data = None
        try:
            import requests
            import os
            weather_api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
            if weather_api_key:
                weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={field.center_lat}&lon={field.center_lng}&appid={weather_api_key}&units=imperial"
                weather_response = requests.get(weather_url, timeout=10)
                if weather_response.status_code == 200:
                    weather_data = weather_response.json()
        except Exception as e:
            logging.warning(f"Failed to fetch weather data: {e}")
        
        # Prepare data for AI analysis
        analysis_context = {
            "field_name": field.name,
            "field_area_acres": round(field_area, 1),
            "total_vegetation_indices": total_indices,
            "successful_analyses": len(successful_indices),
            "successful_indices": successful_indices,
            "failed_indices": [idx for idx, result in analysis_results.items() if not result.get('success')],
            "analysis_date": datetime.utcnow().strftime('%Y-%m-%d'),
            "weather": weather_data,
            "field_coordinates": {
                "center_lat": field.center_lat,
                "center_lng": field.center_lng
            }
        }
        
        # Generate AI insights using OpenAI
        ai_insights = generate_field_ai_insights(analysis_context)
        
        # Store analysis in database
        try:
            new_analysis = FieldAnalysis()
            new_analysis.field_id = field.id
            new_analysis.ai_analysis_data = json.dumps(ai_insights)
            db.session.add(new_analysis)
            field.last_analyzed = datetime.utcnow()
            db.session.commit()
            
            logging.info(f"Comprehensive AI analysis completed for field {field_id}")
        except Exception as e:
            logging.warning(f"Failed to store AI analysis: {e}")
            db.session.rollback()
        
        return jsonify(ai_insights)
        
    except Exception as e:
        logging.error(f"Error in comprehensive AI analysis for field {field_id}: {str(e)}")
        return jsonify({
            'error': f'AI analysis failed: {str(e)}',
            'insights': 'Unable to generate AI insights at this time. Please try again later.',
            'overall_health': 'Unknown',
            'immediate_actions': ['Retry analysis when system is available'],
            'weather_recommendations': ['Monitor field conditions manually']
        }), 500

def generate_field_ai_insights(analysis_context):
    """Generate AI insights using OpenAI based on field analysis data"""
    try:
        import os
        from openai import OpenAI
        
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Create comprehensive prompt for detailed agricultural analysis
        weather_info = ""
        if analysis_context.get('weather'):
            weather = analysis_context['weather']
            weather_info = f"""
        CURRENT WEATHER CONDITIONS:
        - Weather: {weather['weather'][0]['description']}
        - Temperature: {weather['main']['temp']}°F (feels like {weather['main']['feels_like']}°F)
        - Humidity: {weather['main']['humidity']}%
        - Wind Speed: {weather['wind']['speed']} mph
        - Pressure: {weather['main']['pressure']} hPa
        - Visibility: {weather.get('visibility', 'N/A')} meters"""
        else:
            weather_info = "WEATHER CONDITIONS: Data unavailable"

        prompt = f"""
        You are Dr. Sarah Martinez, a leading agricultural consultant with 20+ years experience in precision farming, satellite imagery analysis, and crop management. You specialize in translating complex vegetation index data into actionable farming strategies.

        FIELD ANALYSIS SUMMARY:
        ═══════════════════════
        Field: {analysis_context['field_name']}
        Size: {analysis_context['field_area_acres']} acres
        Location: {analysis_context['field_coordinates']['center_lat']:.4f}°N, {analysis_context['field_coordinates']['center_lng']:.4f}°W
        Analysis Date: {analysis_context['analysis_date']}

        VEGETATION INDEX RESULTS:
        ═══════════════════════
        Total Indices: {analysis_context['total_vegetation_indices']}
        Successfully Generated: {analysis_context['successful_analyses']}/{analysis_context['total_vegetation_indices']}
        ✓ Available: {', '.join(analysis_context['successful_indices']).upper()}
        ✗ Failed: {', '.join(analysis_context['failed_indices']).upper() if analysis_context['failed_indices'] else 'None'}

        {weather_info}

        ANALYSIS CONTEXT:
        ═══════════════════════
        Each vegetation index reveals different aspects of crop health:
        - NDVI: Overall vegetation vigor and biomass
        - NDRE: Chlorophyll content and nitrogen status  
        - MOISTURE: Plant water stress and irrigation needs
        - EVI: Enhanced vegetation detection in dense canopy areas
        - NDWI: Water stress and drought monitoring
        - CHLOROPHYLL: Photosynthetic activity and plant health

        REQUIRED ANALYSIS:
        ═══════════════════════
        As an expert agricultural consultant, provide a comprehensive field assessment. Focus on:

        1. DETAILED CROP HEALTH ASSESSMENT: What do the vegetation indices specifically tell us about crop stress, nutrient deficiencies, water status, and overall plant vigor?

        2. ZONE-SPECIFIC INSIGHTS: Identify which areas of the field need attention and why.

        3. PRECISION AGRICULTURE RECOMMENDATIONS: Specific actions for irrigation timing, fertilizer application rates, and targeted treatments.

        4. WEATHER-INTEGRATED PLANNING: How current and upcoming weather affects immediate and short-term field management decisions.

        5. ECONOMIC IMPACT: Cost-effective solutions and ROI considerations for recommended actions.

        Provide response in JSON format:
        {{
            "overall_health": "Excellent/Good/Moderate/Poor/Critical",
            "overall_health_class": "text-success/text-info/text-warning/text-danger/text-danger",
            "insights": "Write 3-4 detailed sentences analyzing what the combination of vegetation indices reveals about this specific field. Include specific observations about crop stress patterns, water status, nutrient levels, and vegetation vigor. Reference the actual indices generated and what they indicate about field conditions.",
            "farmer_report": "Write 2-3 paragraphs explaining the satellite analysis results in simple, conversational language that any farmer can understand. Imagine you're explaining to a neighbor farmer over coffee. Avoid technical jargon. Start with what the satellite images show about crop health, then explain what this means for the farmer's operations and bottom line, and finish with the most important next steps. Use everyday farming language and practical examples.",
            "immediate_actions": [
                "Specific action 1 with timing (e.g., 'Apply nitrogen fertilizer at 40-60 lbs/acre within next 5-7 days to address chlorophyll deficiency shown in NDRE analysis')",
                "Specific action 2 with method (e.g., 'Implement targeted irrigation in zones showing moisture stress, focus on field sections with NDWI values below optimal range')",
                "Specific action 3 with monitoring (e.g., 'Conduct soil moisture testing in areas showing vegetation stress to confirm satellite observations and adjust irrigation scheduling')"
            ],
            "weather_recommendations": [
                "Weather-specific recommendation 1 (e.g., 'With current humidity at X% and temperature Y°F, adjust irrigation timing to early morning to minimize evaporation losses')",
                "Weather-specific recommendation 2 (e.g., 'Monitor upcoming weather patterns - if rainfall expected within 48 hours, delay planned fertilizer application to prevent nutrient runoff')",
                "Weather-specific recommendation 3 (e.g., 'Current wind conditions at X mph may affect spray application effectiveness - consider timing adjustments for optimal coverage')"
            ],
            "risk_factors": [
                "Specific risk 1 based on vegetation analysis",
                "Specific risk 2 considering weather patterns",
                "Specific risk 3 related to crop management timing"
            ],
            "cost_analysis": [
                "Cost consideration 1 (e.g., 'Estimated $X per acre for recommended nitrogen application')",
                "Cost consideration 2 (e.g., 'ROI analysis: Early intervention could prevent $Y yield loss per acre')",
                "Cost consideration 3 (e.g., 'Budget approximately $Z for targeted irrigation improvements in identified stress zones')"
            ]
        }}

        Be extremely specific, use actual agricultural terminology, include numerical recommendations where appropriate, and provide actionable steps that a farmer can implement immediately.
        """

        response = openai_client.chat.completions.create(
            model="gpt-4o",  # Using latest model as specified in blueprint
            messages=[
                {"role": "system", "content": "You are an expert agricultural consultant specializing in satellite imagery analysis and precision farming. Provide practical, actionable recommendations for farmers."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
            temperature=0.3
        )
        
        ai_response = json.loads(response.choices[0].message.content or "{}")
        
        # Validate and ensure all required fields exist
        required_fields = ['overall_health', 'insights', 'farmer_report', 'immediate_actions', 'weather_recommendations']
        for field in required_fields:
            if field not in ai_response:
                ai_response[field] = get_fallback_response(field)
        
        # Ensure health class is set
        if 'overall_health_class' not in ai_response:
            health_classes = {
                'Excellent': 'text-success',
                'Good': 'text-success', 
                'Moderate': 'text-warning',
                'Poor': 'text-danger',
                'Critical': 'text-danger'
            }
            ai_response['overall_health_class'] = health_classes.get(ai_response.get('overall_health', 'Moderate'), 'text-warning')
        
        return ai_response
        
    except Exception as e:
        logging.error(f"OpenAI analysis failed: {str(e)}")
        return get_fallback_ai_response(analysis_context)

def get_fallback_ai_response(analysis_context):
    """Provide fallback response when AI analysis fails"""
    successful_count = analysis_context['successful_analyses']
    total_count = analysis_context['total_vegetation_indices']
    
    if successful_count >= 4:
        health = "Good"
        health_class = "text-success"
    elif successful_count >= 2:
        health = "Moderate" 
        health_class = "text-warning"
    else:
        health = "Poor"
        health_class = "text-danger"
    
    return {
        "overall_health": health,
        "overall_health_class": health_class,
        "insights": f"Field analysis completed with {successful_count} of {total_count} vegetation indices successfully generated. Multi-spectral analysis provides comprehensive view of crop health, water stress, and vegetation vigor across the {analysis_context['field_area_acres']} acre field.",
        "immediate_actions": [
            "Review generated vegetation index maps for areas of concern",
            "Monitor field zones showing stress indicators",
            "Consider soil testing in areas with poor vegetation health"
        ],
        "weather_recommendations": [
            "Check local weather forecast for irrigation planning",
            "Monitor temperature patterns for crop stress indicators", 
            "Plan field activities around upcoming weather conditions"
        ]
    }

def get_fallback_response(field_name):
    """Get fallback content for missing AI response fields"""
    fallbacks = {
        'overall_health': 'Moderate',
        'insights': 'Field analysis shows varied vegetation health patterns that require monitoring.',
        'farmer_report': 'The satellite images show your field has mixed vegetation health across different areas. Some sections look healthy and green, while others might need attention. This could mean parts of your field are getting enough water and nutrients, but other areas might be stressed. The most important thing right now is to check those weaker spots and see if they need extra irrigation or fertilizer. Focus on the areas that look different from the rest - they could be telling you something important about soil conditions or water distribution.',
        'immediate_actions': ['Monitor field conditions', 'Check irrigation systems', 'Review crop health'],
        'weather_recommendations': ['Monitor weather patterns', 'Plan irrigation accordingly', 'Consider weather timing for field work']
    }
    return fallbacks.get(field_name, 'Analysis data unavailable')

@app.route('/field/<int:field_id>/monitoring', methods=['POST'])
def save_monitoring_settings(field_id):
    """Save automated monitoring settings for a field"""
    try:
        field = Field.query.get_or_404(field_id)
        data = request.get_json()
        
        # Store monitoring settings in field's metadata or create a new table
        # For now, we'll store in a simple JSON format
        monitoring_settings = {
            'frequency': data.get('frequency', 'disabled'),
            'alert_time': data.get('alert_time', '08:00'),
            'notification_email': data.get('notification_email'),
            'urgent_only': data.get('urgent_only', False),
            'weather_alerts': data.get('weather_alerts', True),
            'change_detection': data.get('change_detection', True),
            'enabled': data.get('frequency') != 'disabled',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # You could extend the Field model to include monitoring_settings column
        # For now, we'll use the analysis table to store settings
        settings_analysis = FieldAnalysis()
        settings_analysis.field_id = field.id
        settings_analysis.ai_analysis_data = json.dumps({
            'type': 'monitoring_settings',
            'settings': monitoring_settings
        })
        db.session.add(settings_analysis)
        db.session.commit()
        
        logging.info(f"Monitoring settings saved for field {field_id}: {monitoring_settings['frequency']}")
        
        return jsonify({
            'success': True,
            'message': f"Monitoring configured for {monitoring_settings['frequency']} updates",
            'settings': monitoring_settings
        })
        
    except Exception as e:
        logging.error(f"Error saving monitoring settings for field {field_id}: {str(e)}")
        return jsonify({'error': f'Failed to save monitoring settings: {str(e)}'}), 500

@app.route('/field/<int:field_id>/test-monitoring', methods=['POST'])
def test_field_monitoring(field_id):
    """Run a test monitoring analysis and send email"""
    try:
        field = Field.query.get_or_404(field_id)
        
        # Get monitoring settings
        settings_query = FieldAnalysis.query.filter_by(field_id=field_id)\
            .filter(FieldAnalysis.ai_analysis_data.like('%monitoring_settings%'))\
            .order_by(FieldAnalysis.analysis_date.desc()).first()
        
        if not settings_query:
            return jsonify({'error': 'No monitoring settings configured for this field'}), 400
        
        settings_data = json.loads(settings_query.ai_analysis_data or '{}')
        monitoring_settings = settings_data.get('settings', {})
        notification_email = monitoring_settings.get('notification_email')
        
        if not notification_email:
            return jsonify({'error': 'No notification email configured'}), 400
        
        # Run monitoring analysis
        from automated_monitoring import FieldMonitor
        monitor = FieldMonitor()
        
        if monitor.should_analyze_field(field):
            field_analysis = monitor.analyze_field_changes(field)
            
            # Send test email
            email_sent = monitor.send_email_alert(field_analysis, notification_email)
            
            if email_sent:
                return jsonify({
                    'success': True,
                    'message': f'Test monitoring completed and email sent to {notification_email}',
                    'analysis_summary': {
                        'urgent_alerts': len(field_analysis.get('urgent_alerts', [])),
                        'overall_health': field_analysis.get('ai_insights', {}).get('overall_health', 'Unknown')
                    }
                })
            else:
                return jsonify({'error': 'Monitoring analysis completed but email sending failed'}), 500
        else:
            return jsonify({
                'success': True,
                'message': 'Field was recently analyzed - using cached results for test email'
            })
        
    except Exception as e:
        logging.error(f"Error in test monitoring for field {field_id}: {str(e)}")
        return jsonify({'error': f'Test monitoring failed: {str(e)}'}), 500

@app.route('/api/analyze_field/<int:field_id>', methods=['POST'])
def analyze_field(field_id):
    """Analyze a field using NDVI data and AI recommendations"""
    try:
        field = Field.query.get_or_404(field_id)
        
        # Get polygon coordinates
        coordinates = field.get_polygon_coordinates()
        
        # Fetch NDVI satellite imagery using NDVIFetcher
        logging.info(f"Fetching NDVI data for field {field_id}")
        
        # Calculate bounding box from coordinates
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        bbox = [min(lngs), min(lats), max(lngs), max(lats)]
        
        # Create GeoJSON geometry for polygon masking
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [coord[1], coord[0]] for coord in coordinates
            ] + [[coordinates[0][1], coordinates[0][0]]]]
        }
        
        ndvi_image_data = ndvi_fetcher.fetch_vegetation_index_image(bbox, 'ndvi', geometry=geometry)
        
        if not ndvi_image_data:
            return jsonify({'error': 'Failed to fetch satellite imagery'}), 500
        
        # Cache NDVI image for field
        field.cache_ndvi_image(ndvi_image_data)
        
        # Analyze NDVI image using proper image processing
        from utils.ndvi_analyzer import NDVIAnalyzer
        ndvi_analyzer = NDVIAnalyzer()
        
        # Convert polygon coordinates to proper geometry format for masking
        field_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [coord[1], coord[0]] for coord in coordinates
            ] + [[coordinates[0][1], coordinates[0][0]]]]
        }
        
        # Perform comprehensive NDVI analysis
        ndvi_analysis_results = ndvi_analyzer.analyze_ndvi_image(ndvi_image_data, field_geometry)
        
        # Extract zone statistics and create proper zone data
        zone_statistics = ndvi_analysis_results.get('zone_statistics', {})
        zones = {}
        ndvi_data = {}
        
        # Build zones and NDVI data from actual analysis
        for zone_id, stats in zone_statistics.items():
            zones[zone_id] = {
                'stats': stats,
                'bounds': bbox,
                'health': stats.get('health_classification', 'unknown')
            }
            ndvi_data[zone_id] = stats.get('mean_ndvi', 0.0)
        
        # If no zones were analyzed, create a fallback with field-level data
        if not zones:
            field_stats = ndvi_analysis_results.get('field_statistics', {})
            field_mean_ndvi = field_stats.get('field_mean_ndvi', 0.0)
            zones['field_center'] = {
                'stats': {'mean_ndvi': field_mean_ndvi, 'health_classification': 'unknown'},
                'bounds': bbox,
                'health': 'unknown'
            }
            ndvi_data['field_center'] = field_mean_ndvi
        
        # Initialize services for comprehensive analysis
        weather_service = WeatherService()
        ai_analyzer = AIFieldAnalyzer()
        
        # Prepare field data
        field_data = {
            'name': field.name,
            'center_lat': field.center_lat,
            'center_lng': field.center_lng,
            'area_acres': field.calculate_area_acres(),
            'polygon_coordinates': coordinates,
            'polygon_data': field.polygon_data
        }
        
        # Generate comprehensive AI analysis
        comprehensive_analysis = ai_analyzer.generate_comprehensive_analysis(field_data, ndvi_image_data)
        
        # Extract weather data from comprehensive analysis
        weather_analysis = comprehensive_analysis.get('weather_analysis', {})
        current_weather = weather_analysis.get('current_conditions', {})
        weather_data = {
            "temperature": current_weather.get('temperature', 0),
            "humidity": current_weather.get('humidity', 0),
            "conditions": current_weather.get('description', 'Unknown'),
            "wind_speed": current_weather.get('wind_speed', 0),
            "weather_analysis": weather_analysis
        }
        
        # Extract AI-generated insights
        ai_insights = comprehensive_analysis.get('ai_insights', {})
        ndvi_analysis = comprehensive_analysis.get('ndvi_analysis', {})
        
        # Use AI recommendations or fallback to basic recommendations
        recommendations = ai_insights.get('recommendations', generate_recommendations(ndvi_data, zones))
        
        # Calculate health scores based on NDVI values
        health_scores = {}
        for zone_id, ndvi_value in ndvi_data.items():
            if ndvi_value > 0.6:
                health_scores[zone_id] = 'healthy'
            elif ndvi_value > 0.3:
                health_scores[zone_id] = 'moderate'
            else:
                health_scores[zone_id] = 'stressed'
        
        # Save analysis to database
        analysis = FieldAnalysis()
        analysis.field_id = field_id
        analysis.set_ndvi_data(ndvi_data)
        analysis.set_health_scores(health_scores)
        analysis.set_recommendations(recommendations)
        analysis.set_weather_data(weather_data)
        
        # Store comprehensive analysis using the model method
        try:
            analysis.set_ai_analysis_data(comprehensive_analysis)
        except Exception as e:
            logging.warning(f"Failed to store AI analysis data: {e}")
            analysis.set_ai_analysis_data({})
        
        db.session.add(analysis)
        field.last_analyzed = datetime.utcnow()
        db.session.commit()
        
        logging.info(f"Field {field_id} analyzed successfully with AI insights")
        
        return jsonify({
            'success': True,
            'ndvi_data': ndvi_data,
            'health_scores': health_scores,
            'recommendations': recommendations,
            'weather_data': weather_data,
            'zones': zones,
            'comprehensive_analysis': comprehensive_analysis,
            'ai_insights': ai_insights
        })
        
    except Exception as e:
        logging.error(f"Error analyzing field {field_id}: {str(e)}")
        return jsonify({'error': 'Failed to analyze field'}), 500

@app.route('/api/delete_field/<int:field_id>', methods=['DELETE'])
def delete_field(field_id):
    """Delete a field and its analyses"""
    try:
        field = Field.query.get_or_404(field_id)
        field_name = field.name
        
        db.session.delete(field)
        db.session.commit()
        
        logging.info(f"Field '{field_name}' deleted successfully")
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Error deleting field {field_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete field'}), 500



@app.route('/api/field_comprehensive_analysis/<int:field_id>')
def field_comprehensive_analysis(field_id):
    """Get comprehensive AI analysis data for a field"""
    try:
        field = Field.query.get_or_404(field_id)
        
        # Get the latest analysis with AI data
        latest_analysis = FieldAnalysis.query.filter_by(field_id=field_id)\
                                           .order_by(FieldAnalysis.analysis_date.desc())\
                                           .first()
        
        if not latest_analysis:
            return jsonify({'error': 'No analysis data available'}), 404
        
        # Get comprehensive AI analysis data
        ai_analysis = latest_analysis.get_ai_analysis_data()
        
        # Get current weather data
        weather_service = WeatherService()
        current_weather = weather_service.get_current_weather(field.center_lat, field.center_lng)
        forecast = weather_service.get_weather_forecast(field.center_lat, field.center_lng)
        
        # Format response with all available data
        response_data = {
            'field_info': {
                'id': field.id,
                'name': field.name,
                'area_acres': field.calculate_area_acres(),
                'center_coordinates': [field.center_lat, field.center_lng],
                'last_analyzed': latest_analysis.analysis_date.isoformat()
            },
            'current_weather': current_weather,
            'weather_forecast': forecast[:8] if forecast else [],  # Next 24 hours
            'ai_analysis': ai_analysis,
            'traditional_analysis': {
                'ndvi_data': latest_analysis.get_ndvi_data(),
                'health_scores': latest_analysis.get_health_scores(),
                'recommendations': latest_analysis.get_recommendations(),
                'weather_data': latest_analysis.get_weather_data()
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error fetching comprehensive analysis for field {field_id}: {str(e)}")
        return jsonify({'error': f'Failed to fetch comprehensive analysis: {str(e)}'}), 500

@app.route('/api/field_history/<int:field_id>')
def field_history(field_id):
    """Get analysis history for a field"""
    try:
        field = Field.query.get_or_404(field_id)
        analyses = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).limit(10).all()
        
        history = []
        for analysis in analyses:
            # Include AI analysis summary if available
            ai_data = analysis.get_ai_analysis_data()
            ai_summary = {}
            if ai_data:
                ai_insights = ai_data.get('ai_insights', {})
                performance_metrics = ai_data.get('performance_metrics', {})
                ai_summary = {
                    'health_score': performance_metrics.get('health_score', 0),
                    'productivity_estimate': performance_metrics.get('productivity_estimate', 0),
                    'key_findings': ai_insights.get('key_findings', [])[:3],  # Top 3 findings
                    'priority_actions': ai_insights.get('priority_actions', [])[:2]  # Top 2 actions
                }
            
            history.append({
                'date': analysis.analysis_date.isoformat(),
                'ndvi_data': analysis.get_ndvi_data(),
                'health_scores': analysis.get_health_scores(),
                'recommendations': analysis.get_recommendations(),
                'weather_data': analysis.get_weather_data(),
                'ai_summary': ai_summary
            })
        
        return jsonify({
            'field_name': field.name,
            'history': history
        })
        
    except Exception as e:
        logging.error(f"Error getting field history for {field_id}: {str(e)}")
        return jsonify({'error': 'Failed to get field history'}), 500

@app.route('/field/<int:field_id>/cached_ndvi')
def get_cached_ndvi(field_id):
    """Serve cached NDVI image for a field"""
    field = Field.query.get_or_404(field_id)
    
    if not field.has_cached_ndvi():
        return jsonify({"error": "No cached NDVI image available"}), 404
    
    return Response(
        field.get_cached_ndvi_image(),
        mimetype='image/png',
        headers={
            'Content-Disposition': f'inline; filename="ndvi_{field.name}.png"',
            'Cache-Control': 'public, max-age=86400'
        }
    )

@app.route('/health')
def health_check():
    """API health check endpoint"""
    try:
        # Check if Sentinel Hub is properly configured
        is_configured = auth_handler.is_authenticated()
        return jsonify({
            'status': 'healthy',
            'sentinel_hub_configured': is_configured
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'sentinel_hub_configured': False
        }), 500

@app.route('/ndvi', methods=['GET', 'POST'])
def get_ndvi_image():
    """
    Fetch NDVI image from Sentinel Hub API
    
    GET: Uses default bounding box
    POST: Accepts custom bounding box in JSON format: {"bbox": [lng1, lat1, lng2, lat2]}
    
    Returns:
        PNG image response or error message
    """
    try:
        # Determine bounding box and geometry
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'bbox' not in data:
                return jsonify({"error": "Missing 'bbox' in request JSON"}), 400
            bbox = data['bbox']
            geometry = data.get('geometry')  # Optional polygon geometry
        else:
            bbox = [-122.5, 37.7, -122.3, 37.9]  # Default San Francisco Bay Area
            geometry = None
        
        # Validate bounding box
        if not ndvi_fetcher.validate_bbox(bbox):
            return jsonify({"error": "Invalid bounding box format or coordinates"}), 400
        
        logger.info(f"Fetching NDVI image for bbox: {bbox}")
        
        # Check if credentials are available
        if not auth_handler.is_authenticated():
            logger.error("Sentinel Hub authentication failed")
            return jsonify({
                "error": "Sentinel Hub credentials not configured",
                "message": "Please set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET environment variables"
            }), 503
        
        logger.info("Sentinel Hub authentication successful")
        
        # Check if this is for a saved field and has cached NDVI
        field_id = None
        if request.method == 'POST':
            data = request.get_json() or {}
            field_id = data.get('field_id')
        
        # Try to use cached image if available and fresh
        if field_id:
            try:
                field = Field.query.get(field_id)
                if field and field.has_cached_ndvi() and field.is_ndvi_cache_fresh():
                    logger.info(f"Serving cached NDVI for field {field_id}")
                    return Response(
                        field.get_cached_ndvi_image(),
                        mimetype='image/png',
                        headers={
                            'Content-Disposition': f'inline; filename="ndvi_field_{field_id}.png"',
                            'Cache-Control': 'public, max-age=86400'
                        }
                    )
            except Exception as e:
                logger.warning(f"Could not check cached NDVI: {e}")
        
        # Fetch NDVI image from API
        image_data = ndvi_fetcher.fetch_vegetation_index_image(bbox, 'ndvi', geometry=geometry)
        
        if image_data:
            # Cache the image if this is for an existing saved field
            if field_id:
                try:
                    field = Field.query.get(field_id)
                    if field:
                        field.cache_ndvi_image(image_data)
                        db.session.commit()
                        logger.info(f"Cached NDVI image for field {field_id}")
                except Exception as e:
                    logger.warning(f"Could not cache NDVI: {e}")
            
            return Response(
                image_data,
                mimetype='image/png',
                headers={
                    'Content-Disposition': f'inline; filename="ndvi_{bbox[0]}_{bbox[1]}.png"',
                    'Cache-Control': 'public, max-age=3600'
                }
            )
        else:
            return jsonify({
                "error": "Failed to fetch NDVI image",
                "message": "Could not retrieve satellite data. Check logs for details."
            }), 500
            
    except Exception as e:
        logger.error(f"Error in /ndvi endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/vegetation-index', methods=['POST'])
def get_vegetation_index():
    """
    Fetch vegetation index image from Sentinel Hub API
    
    POST: Accepts bounding box and index type in JSON format:
    {"bbox": [lng1, lat1, lng2, lat2], "index_type": "ndvi", "geometry": {...}}
    
    Returns:
        PNG image response or error message
    """
    try:
        data = request.get_json()
        
        if not data or 'bbox' not in data:
            return jsonify({"error": "Missing bounding box"}), 400
        
        bbox = data['bbox']
        index_type = data.get('index_type', 'ndvi')
        geometry = data.get('geometry')
        
        # Validate index type
        valid_indices = ['ndvi', 'ndre', 'moisture', 'evi', 'ndwi', 'chlorophyll']
        if index_type not in valid_indices:
            return jsonify({"error": f"Invalid index type. Must be one of: {valid_indices}"}), 400
        
        if not ndvi_fetcher.auth.is_authenticated():
            return jsonify({"error": "Sentinel Hub authentication not configured"}), 503
        
        # Validate bbox format
        if not isinstance(bbox, list) or len(bbox) != 4:
            return jsonify({"error": "Invalid bounding box format"}), 400
        
        if not ndvi_fetcher.validate_bbox(bbox):
            return jsonify({"error": "Invalid bounding box coordinates"}), 400
        
        # Fetch vegetation index image from API
        image_data = ndvi_fetcher.fetch_vegetation_index_image(bbox, index_type, geometry=geometry)
        
        if image_data:
            return Response(
                image_data,
                mimetype='image/png',
                headers={
                    'Cache-Control': 'public, max-age=3600',
                    'Content-Type': 'image/png'
                }
            )
        else:
            return jsonify({"error": "Failed to fetch satellite imagery"}), 500
            
    except Exception as e:
        logger.error(f"Error in /vegetation-index endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
