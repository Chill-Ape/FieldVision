"""
Main Flask application for NDVI satellite imagery service
Provides endpoints for fetching and displaying NDVI data from Sentinel Hub
"""

import json
import logging
from datetime import datetime
from flask import Flask, render_template, render_template_string, Response, jsonify, request
from auth import SentinelHubAuth
from ndvi_fetcher import NDVIFetcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize Sentinel Hub components
auth_handler = SentinelHubAuth()
ndvi_fetcher = NDVIFetcher(auth_handler)

# Hardcoded bounding box for testing (San Francisco Bay Area)
# Format: [min_longitude, min_latitude, max_longitude, max_latitude] in EPSG:4326
DEFAULT_BBOX = [-122.5, 37.7, -122.3, 37.9]

@app.route('/')
def index():
    """
    Interactive map interface for NDVI analysis
    Returns modern web interface with map drawing tools
    """
    return render_template('index.html')

@app.route('/sites')
def sites_dashboard():
    """
    Sites management dashboard
    Returns interface for managing saved sites and projects
    """
    return render_template('sites.html')

@app.route('/simple')
def simple_page():
    """
    Simple page with instructions and NDVI viewer button
    Returns basic HTML page for testing the NDVI endpoint
    """
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NDVI Satellite Imagery Service</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background-color: #27ae60;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px 5px;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .btn:hover {
                background-color: #219a52;
            }
            .info-box {
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }
            .credentials-status {
                padding: 10px;
                border-radius: 5px;
                margin: 15px 0;
            }
            .status-ok {
                background-color: #d5f4e6;
                color: #27ae60;
                border: 1px solid #27ae60;
            }
            .status-error {
                background-color: #fadbd8;
                color: #e74c3c;
                border: 1px solid #e74c3c;
            }
            code {
                background-color: #f8f9fa;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛰️ NDVI Satellite Imagery Service</h1>
            
            <div class="credentials-status {{ status_class }}">
                <strong>{{ status_title }}</strong><br>
                {{ status_message }}
            </div>
            
            <div class="info-box">
                <h3>📍 Current Test Area</h3>
                <p><strong>Location:</strong> San Francisco Bay Area</p>
                <p><strong>Bounding Box:</strong> <code>{{ bbox }}</code></p>
                <p><strong>Format:</strong> [min_longitude, min_latitude, max_longitude, max_latitude] in EPSG:4326</p>
            </div>
            
            <div class="info-box">
                <h3>🌱 About NDVI</h3>
                <p>The Normalized Difference Vegetation Index (NDVI) measures vegetation health using satellite imagery. 
                Values range from -1 to 1, where higher values indicate healthier, denser vegetation.</p>
                <ul>
                    <li><strong>Red areas:</strong> Sparse or stressed vegetation</li>
                    <li><strong>Yellow areas:</strong> Moderate vegetation</li>
                    <li><strong>Green areas:</strong> Healthy, dense vegetation</li>
                    <li><strong>Gray areas:</strong> Water, clouds, or bare soil</li>
                </ul>
            </div>
            
            <div class="info-box">
                <h3>🔧 API Endpoints</h3>
                <p><strong>GET /ndvi</strong> - Fetch NDVI image for default bounding box</p>
                <p><strong>POST /ndvi</strong> - Fetch NDVI image for custom bounding box (JSON: {"bbox": [lng1, lat1, lng2, lat2]})</p>
                <p><strong>GET /health</strong> - Check service health and credentials status</p>
            </div>
            
            <a href="/ndvi" class="btn" target="_blank">🌍 View NDVI Image</a>
            <a href="/health" class="btn" style="background-color: #3498db;">📊 Check Service Health</a>
            
            <div class="info-box">
                <h3>🚀 Next Steps</h3>
                <p>This service is ready for integration with map UI components like:</p>
                <ul>
                    <li>Leaflet with drawing tools for custom bounding boxes</li>
                    <li>Mapbox with polygon selection</li>
                    <li>Google Maps with area selection</li>
                </ul>
                <p>Simply replace the hardcoded bbox with user-selected coordinates from the map interface.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Check credentials status for display
    if auth_handler.is_authenticated():
        status_class = "status-ok"
        status_title = "✅ Credentials Configured"
        status_message = "Sentinel Hub API credentials are available. NDVI fetching is enabled."
    else:
        status_class = "status-error"
        status_title = "⚠️ Credentials Missing"
        status_message = "Please set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET environment variables."
    
    return render_template_string(html_template, 
                                bbox=DEFAULT_BBOX,
                                status_class=status_class,
                                status_title=status_title,
                                status_message=status_message)

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
            bbox = DEFAULT_BBOX
            geometry = None
        
        # Validate bounding box
        if not ndvi_fetcher.validate_bbox(bbox):
            return jsonify({"error": "Invalid bounding box format or coordinates"}), 400
        
        logger.info(f"Fetching NDVI image for bbox: {bbox}")
        
        # Check if credentials are available
        if not auth_handler.is_authenticated():
            return jsonify({
                "error": "Sentinel Hub credentials not configured",
                "message": "Please set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET environment variables"
            }), 503
        
        # Check if this is for a saved field and has cached NDVI
        field_id = None
        if request.method == 'POST':
            data = request.get_json() or {}
            field_id = data.get('field_id')
        
        # Try to use cached image if available and fresh
        if field_id:
            try:
                from app import db
                field = db.session.execute(db.text("SELECT * FROM field WHERE id = :id"), {"id": field_id}).fetchone()
                if field:
                    # Check if there's cached NDVI data
                    cached_data = db.session.execute(
                        db.text("SELECT cached_ndvi_image, ndvi_cache_date FROM field WHERE id = :id AND cached_ndvi_image IS NOT NULL"), 
                        {"id": field_id}
                    ).fetchone()
                    
                    if cached_data and cached_data[1]:
                        # Check if cache is fresh (within 30 days)
                        from datetime import timedelta
                        cache_age = datetime.utcnow() - cached_data[1]
                        if cache_age < timedelta(days=30):
                            logger.info(f"Serving cached NDVI for field {field_id}")
                            return Response(
                                cached_data[0],
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
            # Auto-save field with NDVI image if not already saved
            if not field_id and geometry:
                try:
                    from app import db
                    from models import Field
                    
                    # Calculate center point from bbox
                    center_lat = (bbox[1] + bbox[3]) / 2
                    center_lng = (bbox[0] + bbox[2]) / 2
                    
                    # Generate auto-save name
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    auto_name = f"Field_{center_lat:.4f}_{center_lng:.4f}_{timestamp}"
                    
                    # Create new field with NDVI cache
                    field = Field()
                    field.name = auto_name
                    field.center_lat = center_lat
                    field.center_lng = center_lng
                    field.polygon_data = json.dumps(geometry.get('coordinates', [])[0] if geometry else [])
                    field.created_at = datetime.utcnow()
                    field.cached_ndvi_image = image_data
                    field.ndvi_cache_date = datetime.utcnow()
                    
                    db.session.add(field)
                    db.session.commit()
                    
                    logger.info(f"Auto-saved field '{auto_name}' with cached NDVI (ID: {field.id})")
                    
                    # Return field ID in response headers for frontend to use
                    headers = {
                        'Content-Disposition': f'inline; filename="ndvi_{bbox[0]}_{bbox[1]}.png"',
                        'Cache-Control': 'public, max-age=3600',
                        'X-Field-Id': str(field.id),
                        'X-Field-Name': auto_name
                    }
                    
                    return Response(image_data, mimetype='image/png', headers=headers)
                    
                except Exception as e:
                    logger.warning(f"Could not auto-save field: {e}")
            
            # Cache the image if this is for an existing saved field
            elif field_id:
                try:
                    from app import db
                    db.session.execute(
                        db.text("UPDATE field SET cached_ndvi_image = :image_data, ndvi_cache_date = :cache_date WHERE id = :id"),
                        {"image_data": image_data, "cache_date": datetime.utcnow(), "id": field_id}
                    )
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

@app.route('/analyze_field', methods=['POST'])
def analyze_field_with_ai():
    """
    Advanced field analysis with AI recommendations
    Combines NDVI analysis, weather data, and agricultural insights
    """
    try:
        data = request.get_json()
        if not data or 'bbox' not in data:
            return jsonify({"error": "Missing 'bbox' in request JSON"}), 400
        
        bbox = data['bbox']
        geometry = data.get('geometry')
        crop_type = data.get('crop_type', 'grapevine')
        field_id = data.get('field_id')
        
        # Validate inputs
        if not ndvi_fetcher.validate_bbox(bbox):
            return jsonify({"error": "Invalid bounding box format"}), 400
        
        logger.info(f"Starting AI field analysis for bbox: {bbox}")
        
        # Check authentication
        if not auth_handler.is_authenticated():
            return jsonify({
                "error": "Sentinel Hub credentials required",
                "message": "Configure SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET"
            }), 503
        
        # Step 1: Get NDVI image data
        image_data = ndvi_fetcher.fetch_ndvi_image(bbox, geometry=geometry)
        if not image_data:
            return jsonify({"error": "Failed to fetch satellite imagery"}), 500
        
        # Step 2: Analyze NDVI image
        from utils.ndvi_analyzer import analyze_field_ndvi, get_zone_ndvi_values
        ndvi_analysis = analyze_field_ndvi(image_data, geometry)
        zone_ndvi_values = get_zone_ndvi_values(ndvi_analysis)
        
        # Step 3: Get weather data for field location
        center_lat = (bbox[1] + bbox[3]) / 2
        center_lng = (bbox[0] + bbox[2]) / 2
        
        from utils.weather_service import get_comprehensive_weather_data
        try:
            weather_data = get_comprehensive_weather_data(center_lat, center_lng)
        except Exception as e:
            logger.warning(f"Weather data unavailable: {e}")
            weather_data = {
                'current': {'temperature': 20, 'humidity': 60, 'description': 'unavailable'},
                'agricultural_summary': {
                    'total_rainfall_7d': 10, 'avg_temperature_7d': 20,
                    'drought_risk': 'unknown', 'growing_conditions': 'unknown'
                }
            }
        
        # Step 4: Generate AI recommendations
        from utils.recommendation_engine import analyze_field_with_weather
        ai_recommendations = analyze_field_with_weather(zone_ndvi_values, weather_data, crop_type)
        
        # Step 5: Cache results if this is a saved field
        if field_id:
            try:
                from app import db
                db.session.execute(
                    db.text("UPDATE field SET cached_ndvi_image = :image_data, ndvi_cache_date = :cache_date WHERE id = :id"),
                    {"image_data": image_data, "cache_date": datetime.utcnow(), "id": field_id}
                )
                db.session.commit()
                logger.info(f"Cached analysis for field {field_id}")
            except Exception as e:
                logger.warning(f"Could not cache analysis: {e}")
        
        # Return comprehensive analysis
        analysis_results = {
            'success': True,
            'ndvi_analysis': ndvi_analysis,
            'weather_data': weather_data,
            'ai_recommendations': ai_recommendations,
            'field_metadata': {
                'bbox': bbox,
                'center_coordinates': [center_lat, center_lng],
                'crop_type': crop_type,
                'analysis_timestamp': f"{datetime.utcnow().isoformat()}"
            }
        }
        
        return jsonify(analysis_results)
        
    except Exception as e:
        logger.error(f"Error in AI field analysis: {e}")
        return jsonify({"error": "Analysis failed", "message": str(e)}), 500

@app.route('/health')
def health_check():
    """
    Health check endpoint
    Returns service status and configuration info
    """
    return jsonify({
        "status": "healthy",
        "service": "NDVI Satellite Imagery Service",
        "sentinel_hub_configured": auth_handler.is_authenticated(),
        "default_bbox": DEFAULT_BBOX,
        "endpoints": {
            "/": "Main page with instructions",
            "/ndvi": "GET/POST - Fetch NDVI image",
            "/health": "Service health check"
        }
    })

if __name__ == '__main__':
    # Run in debug mode for development
    app.run(host='0.0.0.0', port=5000, debug=True)
