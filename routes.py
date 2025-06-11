from flask import render_template, request, jsonify, flash, redirect, url_for, Response, render_template_string
from app import app, db
from models import Field, FieldAnalysis
from utils.sentinel_hub import fetch_ndvi_image
from utils.ndvi_processor import process_ndvi_data, calculate_field_zones
from utils.ai_recommendations import generate_recommendations
from utils.weather_service import get_weather_data
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
        # For AJAX requests, render only the content block
        full_template = render_template(template_name, **context)
        # Extract content between {% block content %} and {% endblock %}
        # For now, we'll create content-only templates
        content_template = template_name.replace('.html', '_content.html')
        try:
            return render_template(content_template, **context)
        except:
            # Fallback to full template if content template doesn't exist
            return full_template
    else:
        # For regular requests, render full template
        return render_template(template_name, **context)

@app.route('/')
def index():
    """Main page with map interface"""
    return render_spa_template('index_clean.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard showing all saved fields"""
    fields = Field.query.order_by(Field.created_at.desc()).all()
    return render_spa_template('dashboard.html', fields=fields)

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
        fields = Field.query.order_by(Field.created_at.desc()).all()
        logger.info(f"Found {len(fields)} fields for reports page")
        for field in fields:
            logger.info(f"Field: {field.name}, ID: {field.id}")
        return render_spa_template('reports.html', fields=fields)
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        return render_spa_template('reports.html', fields=[])

@app.route('/site/<int:field_id>')
def site_project(field_id):
    """Individual site project page with comprehensive data and controls"""
    field = Field.query.get_or_404(field_id)
    latest_analysis = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).first()
    
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
        
        # Fetch NDVI image (REQUIRED - site cannot be saved without NDVI)
        ndvi_image_bytes = ndvi_fetcher.fetch_ndvi_image(bbox, geometry=geometry)
        
        if not ndvi_image_bytes:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Failed to generate NDVI image. Site cannot be saved without satellite data.'}), 500
        
        # Cache the NDVI image
        field.cache_ndvi_image(ndvi_image_bytes)
        field.last_analyzed = datetime.utcnow()
        
        # Update the field in database with cached NDVI
        db.session.add(field)
        
        # Analyze NDVI data
        analysis_results = analyze_field_ndvi(ndvi_image_bytes, geometry)
        
        # Generate AI recommendations
        zone_ndvi_values = get_zone_ndvi_values(analysis_results)
        recommendations = generate_recommendations(zone_ndvi_values, analysis_results.get('zones', {}))
        
        # Create initial field analysis record
        analysis = FieldAnalysis()
        analysis.field_id = field.id
        analysis.set_ndvi_data(zone_ndvi_values)
        analysis.set_health_scores(analysis_results.get('zone_stats', {}))
        analysis.set_recommendations(recommendations)
        analysis.analysis_date = datetime.utcnow()
        
        db.session.add(analysis)
        db.session.commit()
        
        logging.info(f"Generated initial NDVI analysis for field '{field.name}'")
        
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
        
        # Fetch NDVI satellite imagery
        logging.info(f"Fetching NDVI data for field {field_id}")
        ndvi_image_data = fetch_ndvi_image(coordinates)
        
        if not ndvi_image_data:
            return jsonify({'error': 'Failed to fetch satellite imagery'}), 500
        
        # Calculate field zones (3x3 grid)
        zones = calculate_field_zones(coordinates)
        
        # Process NDVI data for each zone
        ndvi_data = process_ndvi_data(ndvi_image_data, zones)
        
        # Generate AI recommendations
        recommendations = generate_recommendations(ndvi_data, zones)
        
        # Get weather data
        weather_data = get_weather_data(field.center_lat, field.center_lng)
        
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
        analysis = FieldAnalysis(field_id=field_id)
        analysis.set_ndvi_data(ndvi_data)
        analysis.set_health_scores(health_scores)
        analysis.set_recommendations(recommendations)
        analysis.set_weather_data(weather_data)
        
        db.session.add(analysis)
        field.last_analyzed = datetime.utcnow()
        db.session.commit()
        
        logging.info(f"Field {field_id} analyzed successfully")
        
        return jsonify({
            'success': True,
            'ndvi_data': ndvi_data,
            'health_scores': health_scores,
            'recommendations': recommendations,
            'weather_data': weather_data,
            'zones': zones
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



@app.route('/api/field_history/<int:field_id>')
def field_history(field_id):
    """Get analysis history for a field"""
    try:
        field = Field.query.get_or_404(field_id)
        analyses = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).limit(10).all()
        
        history = []
        for analysis in analyses:
            history.append({
                'date': analysis.analysis_date.isoformat(),
                'ndvi_data': analysis.get_ndvi_data(),
                'health_scores': analysis.get_health_scores(),
                'recommendations': analysis.get_recommendations(),
                'weather_data': analysis.get_weather_data()
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
