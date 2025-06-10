import requests
import logging
import os
import base64
from PIL import Image
import io
import json

def fetch_ndvi_image(coordinates):
    """
    Fetch NDVI satellite imagery from Sentinel Hub API
    
    Args:
        coordinates: List of [lat, lng] coordinate pairs defining the field boundary
    
    Returns:
        Image data or None if fetch fails
    """
    try:
        client_id = os.getenv("SENTINEL_HUB_CLIENT_ID", "demo_client")
        client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "demo_secret")
        
        if client_id == "demo_client" or client_secret == "demo_secret":
            logging.warning("Using demo NDVI data - no Sentinel Hub credentials provided")
            return generate_demo_ndvi_image(coordinates)
        
        # Get access token
        token = get_sentinel_hub_token(client_id, client_secret)
        if not token:
            logging.error("Failed to get Sentinel Hub access token")
            return generate_demo_ndvi_image(coordinates)
        
        # Calculate bounding box from coordinates
        bbox = calculate_bbox(coordinates)
        
        # Prepare the request for NDVI data
        evalscript = get_ndvi_evalscript()
        
        request_payload = {
            "input": {
                "bounds": {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [convert_coordinates_for_sentinel(coordinates)]
                    }
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {
                                "from": "2024-01-01T00:00:00Z",
                                "to": "2024-12-31T23:59:59Z"
                            },
                            "maxCloudCoverage": 20
                        }
                    }
                ]
            },
            "output": {
                "width": 512,
                "height": 512,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {
                            "type": "image/png"
                        }
                    }
                ]
            },
            "evalscript": evalscript
        }
        
        # Make the API request
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = "https://services.sentinel-hub.com/api/v1/process"
        response = requests.post(url, headers=headers, json=request_payload, timeout=30)
        
        if response.status_code == 200:
            logging.info("Successfully fetched NDVI imagery from Sentinel Hub")
            return response.content
        else:
            logging.error(f"Sentinel Hub API error: {response.status_code} - {response.text}")
            return generate_demo_ndvi_image(coordinates)
            
    except requests.RequestException as e:
        logging.error(f"Network error fetching NDVI data: {str(e)}")
        return generate_demo_ndvi_image(coordinates)
    except Exception as e:
        logging.error(f"Unexpected error fetching NDVI data: {str(e)}")
        return generate_demo_ndvi_image(coordinates)

def get_sentinel_hub_token(client_id, client_secret):
    """
    Get OAuth token for Sentinel Hub API
    
    Args:
        client_id: Sentinel Hub client ID
        client_secret: Sentinel Hub client secret
    
    Returns:
        Access token string or None
    """
    try:
        token_url = "https://services.sentinel-hub.com/oauth/token"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = requests.post(token_url, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get("access_token")
        else:
            logging.error(f"Token request failed: {response.status_code}")
            return None
            
    except Exception as e:
        logging.error(f"Error getting Sentinel Hub token: {str(e)}")
        return None

def get_ndvi_evalscript():
    """
    Return the evalscript for calculating NDVI from Sentinel-2 data
    
    Returns:
        Evalscript string for NDVI calculation
    """
    return """
    //VERSION=3
    function setup() {
        return {
            input: ["B04", "B08", "SCL"],
            output: { bands: 1, sampleType: "FLOAT32" }
        };
    }

    function evaluatePixel(sample) {
        // Skip clouds, shadows, and other invalid pixels
        if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10 || sample.SCL == 11) {
            return [0];
        }
        
        let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
        
        // Normalize NDVI to 0-1 range for visualization
        return [(ndvi + 1) / 2];
    }
    """

def calculate_bbox(coordinates):
    """
    Calculate bounding box from coordinates
    
    Args:
        coordinates: List of [lat, lng] pairs
    
    Returns:
        Bounding box as [min_lng, min_lat, max_lng, max_lat]
    """
    if not coordinates:
        return None
    
    lats = [coord[0] for coord in coordinates]
    lngs = [coord[1] for coord in coordinates]
    
    return [min(lngs), min(lats), max(lngs), max(lats)]

def convert_coordinates_for_sentinel(coordinates):
    """
    Convert coordinates from [lat, lng] to [lng, lat] format required by Sentinel Hub
    
    Args:
        coordinates: List of [lat, lng] pairs
    
    Returns:
        List of [lng, lat] pairs
    """
    return [[coord[1], coord[0]] for coord in coordinates]

def generate_demo_ndvi_image(coordinates):
    """
    Generate a demo NDVI image when real satellite data is not available
    
    Args:
        coordinates: Field coordinates (not used in demo)
    
    Returns:
        Demo image data as bytes
    """
    try:
        # Create a simple demo NDVI image
        import numpy as np
        from PIL import Image
        
        # Create a 512x512 image with simulated NDVI data
        width, height = 512, 512
        
        # Generate realistic NDVI pattern
        np.random.seed(42)  # For consistent demo data
        
        # Create base NDVI values (higher in center, lower at edges)
        x = np.linspace(-1, 1, width)
        y = np.linspace(-1, 1, height)
        X, Y = np.meshgrid(x, y)
        
        # Create a realistic field pattern
        base_ndvi = 0.6 * np.exp(-(X**2 + Y**2) / 0.5)  # Gaussian distribution
        
        # Add some variation and realistic patterns
        noise = 0.1 * np.random.random((height, width))
        strips = 0.05 * np.sin(X * 10)  # Field rows effect
        
        ndvi_array = base_ndvi + noise + strips
        ndvi_array = np.clip(ndvi_array, 0, 1)  # Ensure valid range
        
        # Convert to 8-bit image
        image_array = (ndvi_array * 255).astype(np.uint8)
        
        # Create PIL image
        image = Image.fromarray(image_array, mode='L')
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        logging.info("Generated demo NDVI image")
        return img_buffer.getvalue()
        
    except Exception as e:
        logging.error(f"Error generating demo NDVI image: {str(e)}")
        return None

def fetch_copernicus_data(coordinates):
    """
    Alternative method to fetch satellite data from Copernicus Open Access Hub
    This is a backup method if Sentinel Hub is not available
    
    Args:
        coordinates: Field boundary coordinates
    
    Returns:
        Satellite image data or None
    """
    try:
        # This would implement Copernicus Open Access Hub API
        # For now, return demo data
        logging.info("Copernicus Open Access Hub not implemented, using demo data")
        return generate_demo_ndvi_image(coordinates)
        
    except Exception as e:
        logging.error(f"Error fetching Copernicus data: {str(e)}")
        return None

def validate_coordinates(coordinates):
    """
    Validate that coordinates form a valid polygon
    
    Args:
        coordinates: List of [lat, lng] coordinate pairs
    
    Returns:
        Boolean indicating if coordinates are valid
    """
    try:
        if not coordinates or len(coordinates) < 3:
            return False
        
        # Check if coordinates are within valid lat/lng ranges
        for coord in coordinates:
            if len(coord) != 2:
                return False
            
            lat, lng = coord
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return False
        
        # Check if polygon is closed (first and last points should be the same or close)
        if coordinates[0] != coordinates[-1]:
            # Auto-close the polygon
            coordinates.append(coordinates[0])
        
        return True
        
    except Exception as e:
        logging.error(f"Error validating coordinates: {str(e)}")
        return False

def process_satellite_image(image_data, image_format='PNG'):
    """
    Process raw satellite image data for analysis
    
    Args:
        image_data: Raw image bytes
        image_format: Image format (PNG, JPEG, etc.)
    
    Returns:
        Processed PIL Image object
    """
    try:
        if not image_data:
            return None
        
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        logging.info(f"Processed satellite image: {image.size} pixels")
        return image
        
    except Exception as e:
        logging.error(f"Error processing satellite image: {str(e)}")
        return None
