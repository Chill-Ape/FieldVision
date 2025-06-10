"""
Main Flask application for NDVI satellite imagery service
Provides endpoints for fetching and displaying NDVI data from Sentinel Hub
"""

import logging
from flask import Flask, render_template_string, Response, jsonify, request
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
    Main page with instructions and NDVI viewer button
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
        # Determine bounding box
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'bbox' not in data:
                return jsonify({"error": "Missing 'bbox' in request JSON"}), 400
            bbox = data['bbox']
        else:
            bbox = DEFAULT_BBOX
        
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
        
        # Fetch NDVI image
        image_data = ndvi_fetcher.fetch_ndvi_image(bbox)
        
        if image_data:
            return Response(
                image_data,
                mimetype='image/png',
                headers={
                    'Content-Disposition': f'inline; filename="ndvi_{bbox[0]}_{bbox[1]}.png"',
                    'Cache-Control': 'no-cache'
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
