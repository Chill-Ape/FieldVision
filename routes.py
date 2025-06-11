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
            ndvi_image_bytes = ndvi_fetcher.fetch_ndvi_image(bbox, geometry=geometry)
            
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
        
        ndvi_image_data = ndvi_fetcher.fetch_ndvi_image(bbox, geometry=geometry)
        
        if not ndvi_image_data:
            return jsonify({'error': 'Failed to fetch satellite imagery'}), 500
        
        # Cache NDVI image for field
        field.cache_ndvi_image(ndvi_image_data)
        
        # Create basic zone data for compatibility
        zones = {
            'zone_1': {'center': [coordinates[0][0], coordinates[0][1]], 'bounds': bbox},
            'zone_2': {'center': [coordinates[1][0] if len(coordinates) > 1 else coordinates[0][0], 
                                coordinates[1][1] if len(coordinates) > 1 else coordinates[0][1]], 'bounds': bbox},
            'zone_3': {'center': [coordinates[2][0] if len(coordinates) > 2 else coordinates[0][0], 
                                coordinates[2][1] if len(coordinates) > 2 else coordinates[0][1]], 'bounds': bbox}
        }
        
        # Create basic NDVI data structure
        ndvi_data = {
            'zone_1': 0.65,  # Healthy vegetation baseline
            'zone_2': 0.72,
            'zone_3': 0.58
        }
        
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
        image_data = ndvi_fetcher.fetch_ndvi_image(bbox, geometry=geometry)
        
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
