from flask import render_template, request, jsonify, flash, redirect, url_for, Response, render_template_string
from app import app, db
from models import Field, FieldAnalysis, AIInsight
from utils.sentinel_hub import fetch_ndvi_image
from utils.ndvi_processor import process_ndvi_data, calculate_field_zones
from utils.ai_recommendations import generate_recommendations
from utils.ai_insights import AgricultureAI, get_ai_insights, get_portfolio_insights
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
        # For AJAX requests, return the full template
        # The JavaScript in base.html will handle extracting the content
        return render_template(template_name, **context)
    else:
        # For regular requests, render full template
        return render_template(template_name, **context)

@app.route('/')
def index():
    """Main page with map interface"""
    edit_field_id = request.args.get('edit')
    edit_field = None
    
    if edit_field_id:
        try:
            edit_field = Field.query.get(int(edit_field_id))
        except (ValueError, TypeError):
            edit_field = None
    
    return render_template('index_clean.html', edit_field=edit_field)

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
        
        # Fetch NDVI satellite imagery using proper API
        logging.info(f"Fetching real satellite NDVI data for field {field_id}")
        
        from auth import SentinelHubAuth
        from ndvi_fetcher import NDVIFetcher
        
        # Initialize authentication and fetcher
        auth = SentinelHubAuth()
        if not auth.is_authenticated():
            return jsonify({'error': 'Sentinel Hub API credentials not configured. Please check your API keys.'}), 500
            
        fetcher = NDVIFetcher(auth)
        
        # Calculate bounding box from coordinates
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        bbox = [min(lngs), min(lats), max(lngs), max(lats)]
        
        # Create GeoJSON geometry for masking
        geometry = {
            "type": "Polygon",
            "coordinates": [[[lng, lat] for lat, lng in coordinates]]
        }
        
        # Fetch real NDVI imagery
        ndvi_image_data = fetcher.fetch_ndvi_image(bbox, geometry=geometry)
        
        if not ndvi_image_data:
            return jsonify({'error': 'Failed to fetch satellite imagery. Please verify your Sentinel Hub API credentials and try again.'}), 500
        
        # Cache the NDVI image for this field
        field.cache_ndvi_image(ndvi_image_data)
        
        # Calculate field zones (3x3 grid)
        zones = calculate_field_zones(coordinates)
        
        # Process real NDVI data for each zone with accurate geometric mapping
        ndvi_data = process_ndvi_data(ndvi_image_data, zones, field_coordinates=coordinates, field_bbox=bbox)
        
        if not ndvi_data:
            return jsonify({'error': 'Failed to process satellite imagery data'}), 500
        
        # Generate AI recommendations from real data
        recommendations = generate_recommendations(ndvi_data, zones)
        
        # Get weather data
        weather_data = get_weather_data(field.center_lat, field.center_lng)
        
        # Calculate health scores based on NDVI values
        health_scores = {}
        for zone_id, ndvi_value in ndvi_data.items():
            # Store the actual NDVI value for template access
            health_scores[zone_id] = ndvi_value
        
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

@app.route('/api/update_field/<int:field_id>', methods=['PUT'])
def update_field(field_id):
    """Update an existing field's polygon data"""
    try:
        field = Field.query.get_or_404(field_id)
        data = request.get_json()
        
        # Validate input data
        if not data or 'name' not in data or 'polygon' not in data:
            return jsonify({'success': False, 'message': 'Invalid data provided'}), 400
        
        # Parse polygon coordinates
        try:
            coordinates = json.loads(data['polygon'])
            if not coordinates or len(coordinates) < 3:
                return jsonify({'success': False, 'message': 'Invalid polygon coordinates'}), 400
        except (json.JSONDecodeError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid polygon format'}), 400
        
        # Update field data
        field.name = data['name']
        field.set_polygon_coordinates(coordinates)
        field.center_lat = data.get('center_lat', field.center_lat)
        field.center_lng = data.get('center_lng', field.center_lng)
        
        db.session.commit()
        
        logging.info(f"Field '{field.name}' (ID: {field_id}) updated successfully")
        
        return jsonify({
            'success': True,
            'field_id': field_id,
            'message': 'Field updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating field {field_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to update field'}), 500

@app.route('/api/delete_ai_insight/<int:insight_id>', methods=['DELETE'])
def delete_ai_insight(insight_id):
    """Delete an AI insight"""
    try:
        insight = AIInsight.query.get_or_404(insight_id)
        field_name = insight.field.name
        
        db.session.delete(insight)
        db.session.commit()
        
        logging.info(f"AI insight deleted for field '{field_name}'")
        return jsonify({'success': True, 'message': 'AI insight deleted successfully'})
        
    except Exception as e:
        logging.error(f"Error deleting AI insight {insight_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to delete AI insight'}), 500

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


@app.route('/generate_ai_insights/<int:field_id>', methods=['POST'])
def generate_ai_insights(field_id):
    """Generate AI-powered insights for a specific field"""
    try:
        field = Field.query.get_or_404(field_id)
        
        # Check if AI insight was already generated today for this field
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        existing_insight = AIInsight.query.filter(
            AIInsight.field_id == field_id,
            AIInsight.analysis_date >= today,
            AIInsight.analysis_date < today + timedelta(days=1)
        ).first()
        
        if existing_insight:
            return jsonify({
                'error': 'AI insight already generated today for this field. Only one AI analysis per day is allowed.',
                'existing_insight_id': existing_insight.id
            }), 400
        
        # Get the latest analysis for this field
        latest_analysis = FieldAnalysis.query.filter_by(field_id=field_id).order_by(FieldAnalysis.analysis_date.desc()).first()
        
        if not latest_analysis:
            return jsonify({'error': 'No field analysis available. Please analyze the field first.'}), 400
        
        # Prepare field data for AI analysis using actual data
        field_data = {
            'id': field.id,
            'name': field.name,
            'area_acres': field.calculate_area_acres(),
            'center_lat': field.center_lat,
            'center_lng': field.center_lng,
            'last_analyzed': field.last_analyzed.isoformat() if field.last_analyzed else None
        }
        
        # Extract actual NDVI statistics from the latest analysis
        ndvi_data = latest_analysis.get_ndvi_data() or {}
        health_scores = latest_analysis.get_health_scores() or {}
        
        # Verify we have real NDVI data before proceeding
        if not ndvi_data:
            return jsonify({'error': 'No NDVI data available for this field. Please run "Update NDVI Analysis" first to generate satellite data.'}), 400
        
        # Calculate statistics from actual data
        ndvi_values = []
        for zone_data in ndvi_data.values():
            if isinstance(zone_data, dict) and 'ndvi' in zone_data:
                ndvi_values.append(zone_data['ndvi'])
            elif isinstance(zone_data, (int, float)):
                ndvi_values.append(zone_data)
        
        if not ndvi_values:
            return jsonify({'error': 'Invalid NDVI data format. Please regenerate field analysis.'}), 400
            
        mean_ndvi = sum(ndvi_values) / len(ndvi_values)
        min_ndvi = min(ndvi_values)
        max_ndvi = max(ndvi_values)
        std_ndvi = (sum((x - mean_ndvi) ** 2 for x in ndvi_values) / len(ndvi_values)) ** 0.5
        
        # Prepare analysis data for AI
        analysis_data = {
            'field_stats': {
                'mean_ndvi': mean_ndvi,
                'min_ndvi': min_ndvi,
                'max_ndvi': max_ndvi,
                'std_ndvi': std_ndvi
            },
            'zone_stats': ndvi_data,
            'health_scores': health_scores,
            'recommendations': latest_analysis.get_recommendations() or []
        }
        
        # Generate AI insights
        ai_insights = get_ai_insights(field_data, analysis_data)
        
        # Save insights to database
        insight = AIInsight(
            field_id=field_id,
            insight_type='field_health',
            confidence_score=ai_insights.get('confidence_score', 0.7),
            data_quality=ai_insights.get('data_quality', 'Good')
        )
        insight.set_ai_analysis(ai_insights)
        
        db.session.add(insight)
        db.session.commit()
        
        logging.info(f"AI insight generated for field '{field.name}' (ID: {field_id})")
        
        return jsonify({
            'success': True,
            'insight_id': insight.id,
            'insights': ai_insights
        })
        
    except Exception as e:
        logging.error(f"Error generating AI insights: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/ai_insights/<int:field_id>')
def view_ai_insights(field_id):
    """View AI insights for a specific field"""
    field = Field.query.get_or_404(field_id)
    
    # Get latest AI insights
    latest_insights = AIInsight.query.filter_by(field_id=field_id).order_by(AIInsight.analysis_date.desc()).all()
    
    return render_template('ai_insights.html', 
                         field=field, 
                         insights=latest_insights)


@app.route('/portfolio_ai_insights')
def portfolio_ai_insights():
    """Generate portfolio-level AI insights for all fields"""
    try:
        # Get all fields with their latest analyses
        fields = Field.query.all()
        fields_data = []
        
        for field in fields:
            latest_analysis = FieldAnalysis.query.filter_by(field_id=field.id).order_by(FieldAnalysis.analysis_date.desc()).first()
            
            field_info = {
                'id': field.id,
                'name': field.name,
                'area_acres': field.calculate_area_acres(),
                'last_analyzed': field.last_analyzed.isoformat() if field.last_analyzed else None,
                'latest_analysis': {
                    'field_stats': {
                        'mean_ndvi': 0.65  # Extract from actual analysis
                    }
                } if latest_analysis else None
            }
            fields_data.append(field_info)
        
        # Generate portfolio insights
        portfolio_insights = get_portfolio_insights(fields_data)
        
        return render_template('portfolio_insights.html', 
                             fields=fields,
                             portfolio_insights=portfolio_insights)
        
    except Exception as e:
        logger.error(f"Error generating portfolio insights: {e}")
        flash(f"Error generating portfolio insights: {str(e)}", 'error')
        return redirect(url_for('reports'))
