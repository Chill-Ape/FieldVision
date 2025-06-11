"""
NDVI fetcher module for Sentinel Hub API
Handles NDVI image requests and processing
"""

import requests
import logging
import numpy as np
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from auth import SentinelHubAuth

logger = logging.getLogger(__name__)

class NDVIFetcher:
    """Handles NDVI data fetching from Sentinel Hub API"""
    
    def __init__(self, auth_handler: SentinelHubAuth):
        """
        Initialize NDVI fetcher
        
        Args:
            auth_handler: Configured SentinelHubAuth instance
        """
        self.auth = auth_handler
        self.process_url = "https://services.sentinel-hub.com/api/v1/process"
    
    def get_ndvi_evalscript(self) -> str:
        """
        Return the evalscript for calculating NDVI from Sentinel-2 data
        
        Returns:
            Evalscript string for NDVI calculation
        """
        return """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["B04", "B08", "SCL"],
            units: "DN"
        }],
        output: {
            bands: 3,
            sampleType: "AUTO"
        }
    };
}

function evaluatePixel(sample) {
    // B04 = Red, B08 = NIR
    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
    
    // Mask clouds using Scene Classification Layer (SCL)
    if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10 || sample.SCL == 11) {
        // Cloud shadows, medium/high probability clouds, thin cirrus, snow
        return [0.4, 0.4, 0.4]; // Dark gray for masked pixels
    }
    
    // Agricultural stress detection color mapping
    if (ndvi < -0.3) return [0.2, 0.2, 0.4]; // Deep water - dark blue
    if (ndvi < -0.1) return [0.4, 0.4, 0.6]; // Shallow water - blue
    if (ndvi < 0.05) return [0.8, 0.7, 0.6]; // Bare soil/sand - tan
    if (ndvi < 0.1) return [1.0, 0.2, 0.2]; // Critical stress/dying vegetation - bright red
    if (ndvi < 0.15) return [1.0, 0.4, 0.2]; // Severe stress - red-orange
    if (ndvi < 0.2) return [1.0, 0.6, 0.2]; // Moderate stress - orange
    if (ndvi < 0.25) return [1.0, 0.8, 0.2]; // Mild stress - yellow-orange
    if (ndvi < 0.3) return [1.0, 1.0, 0.2]; // Early stress - yellow
    if (ndvi < 0.35) return [0.8, 1.0, 0.2]; // Recovery/low vigor - light green
    if (ndvi < 0.45) return [0.6, 0.9, 0.1]; // Moderate health - green
    if (ndvi < 0.55) return [0.4, 0.8, 0.1]; // Good health - darker green
    if (ndvi < 0.65) return [0.2, 0.7, 0.1]; // Very healthy - dark green
    if (ndvi < 0.75) return [0.1, 0.6, 0.1]; // Excellent health - very dark green
    return [0.05, 0.4, 0.05]; // Peak health - deepest green
}
"""
    
    def create_request_payload(self, bbox: List[float], width: int = 2500, height: int = 2500, geometry: Optional[dict] = None) -> dict:
        """
        Create the request payload for Sentinel Hub Process API
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            width: Output image width in pixels
            height: Output image height in pixels
            geometry: Optional field polygon geometry for precise area analysis
            
        Returns:
            Dictionary containing the complete request payload
        """
        # Calculate time range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Use field geometry if provided, otherwise use bounding box
        if geometry and geometry.get('type') == 'Polygon':
            bounds_geometry = geometry
        else:
            # Fall back to bounding box rectangle
            bounds_geometry = {
                "type": "Polygon",
                "coordinates": [[
                    [bbox[0], bbox[1]],  # min_lng, min_lat
                    [bbox[2], bbox[1]],  # max_lng, min_lat
                    [bbox[2], bbox[3]],  # max_lng, max_lat
                    [bbox[0], bbox[3]],  # min_lng, max_lat
                    [bbox[0], bbox[1]]   # close polygon
                ]]
            }
        
        return {
            "input": {
                "bounds": {
                    "geometry": bounds_geometry,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                    },
                    "bbox": bbox
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                            "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
                        },
                        "maxCloudCoverage": 20
                    }
                }]
            },
            "output": {
                "width": width,
                "height": height,
                "responses": [{
                    "identifier": "default",
                    "format": {
                        "type": "image/png"
                    }
                }]
            },
            "evalscript": self.get_ndvi_evalscript()
        }
    
    def fetch_ndvi_image(self, bbox: List[float], width: int = 2500, height: int = 2500, geometry: Optional[dict] = None) -> Optional[bytes]:
        """
        Fetch NDVI image for the given bounding box with proper aspect ratio
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat] in EPSG:4326
            width: Output image width in pixels (auto-calculated if None)
            height: Output image height in pixels (auto-calculated if None)
            geometry: Optional GeoJSON geometry for polygon masking
            
        Returns:
            PNG image bytes or None if request fails
        """
        # Calculate proper dimensions based on geographic aspect ratio
        # Always recalculate for optimal aspect ratio unless both dimensions are explicitly provided
        if width == 2500 and height == 2500:
            width, height = self._calculate_optimal_dimensions(bbox)
        
        logger.info(f"Using image dimensions: {width}x{height} for bbox: {bbox}")
        # Get access token
        token = self.auth.get_access_token()
        if not token:
            logger.error("Failed to obtain access token")
            return None
        
        # Create request payload with calculated dimensions and geometry
        payload = self.create_request_payload(bbox, width, height, geometry)
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'image/png'
        }
        
        try:
            logger.info(f"Requesting NDVI image for bbox: {bbox}")
            response = requests.post(
                self.process_url,
                json=payload,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully fetched NDVI image ({len(response.content)} bytes)")
                
                # Apply polygon masking if geometry is provided
                if geometry:
                    return self._apply_polygon_mask(response.content, bbox, geometry, width, height)
                
                return response.content
            else:
                logger.error(f"Failed to fetch NDVI image: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NDVI image: {e}")
            return None
    
    def validate_bbox(self, bbox: List[float]) -> bool:
        """
        Validate bounding box coordinates
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            
        Returns:
            True if bbox is valid, False otherwise
        """
        if len(bbox) != 4:
            return False
        
        min_lng, min_lat, max_lng, max_lat = bbox
        
        # Check coordinate ranges
        if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
            return False
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            return False
        
        # Check bbox is properly ordered
        if min_lng >= max_lng or min_lat >= max_lat:
            return False
        
        # Check bbox is not too large (max 0.5 degrees for demo)
        if (max_lng - min_lng) > 0.5 or (max_lat - min_lat) > 0.5:
            logger.warning("Bounding box is quite large, consider reducing size for better performance")
        
        return True
    
    def _calculate_optimal_dimensions(self, bbox: List[float]) -> tuple:
        """
        Calculate optimal image dimensions based on geographic aspect ratio
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            
        Returns:
            Tuple of (width, height) in pixels
        """
        min_lng, min_lat, max_lng, max_lat = bbox
        
        # Calculate geographic dimensions
        lng_diff = max_lng - min_lng
        lat_diff = max_lat - min_lat
        
        # Convert to approximate meters using Haversine formula at center latitude
        center_lat = (min_lat + max_lat) / 2
        lat_rad = math.radians(center_lat)
        
        # Meters per degree longitude at this latitude
        meters_per_deg_lng = 111320 * math.cos(lat_rad)
        meters_per_deg_lat = 111320
        
        # Calculate actual distances in meters
        width_meters = lng_diff * meters_per_deg_lng
        height_meters = lat_diff * meters_per_deg_lat
        
        # Calculate aspect ratio
        aspect_ratio = width_meters / height_meters
        
        # Target maximum dimension for high resolution
        max_dimension = 2500
        
        if aspect_ratio > 1:
            # Wider than tall
            width = max_dimension
            height = int(max_dimension / aspect_ratio)
        else:
            # Taller than wide
            height = max_dimension
            width = int(max_dimension * aspect_ratio)
        
        # Ensure minimum dimensions for quality
        width = max(width, 512)
        height = max(height, 512)
        
        # Ensure maximum dimensions don't exceed API limits
        width = min(width, 2500)
        height = min(height, 2500)
        
        return width, height
    
    def _apply_polygon_mask(self, image_bytes: bytes, bbox: List[float], geometry: dict, width: int, height: int) -> bytes:
        """
        Apply polygon masking to NDVI image to show data only within selected polygon
        
        Args:
            image_bytes: Original NDVI image bytes
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            geometry: GeoJSON geometry containing polygon coordinates
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Masked image bytes
        """
        try:
            # Load the original image
            img = Image.open(BytesIO(image_bytes))
            original_width, original_height = img.size
            
            # Use the actual image dimensions instead of the requested dimensions
            # This preserves the original image quality
            width, height = original_width, original_height
            
            # Convert to RGBA for transparency support
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create a high-quality mask with anti-aliasing
            mask = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(mask)
            
            # Extract polygon coordinates
            if geometry.get('type') == 'Polygon':
                coordinates = geometry['coordinates'][0]  # First ring (exterior)
            else:
                logger.warning("Geometry is not a polygon, skipping mask")
                return image_bytes
            
            # Convert geo coordinates to pixel coordinates with higher precision
            min_lng, min_lat, max_lng, max_lat = bbox
            pixel_coords = []
            
            for coord in coordinates:
                lng, lat = coord
                # Convert to pixel coordinates with float precision
                x = ((lng - min_lng) / (max_lng - min_lng)) * width
                y = ((max_lat - lat) / (max_lat - min_lat)) * height
                pixel_coords.append((x, y))
            
            # Draw the polygon mask with anti-aliasing
            draw.polygon(pixel_coords, fill=255)
            
            # Apply mask using paste method for better quality preservation
            # Create a transparent background
            result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            
            # Use the mask to composite the original image onto transparent background
            result.paste(img, (0, 0), mask)
            
            # Save to bytes with high quality
            output = BytesIO()
            result.save(output, format='PNG', optimize=False, compress_level=1)
            
            logger.info("Successfully applied polygon mask to NDVI image")
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error applying polygon mask: {e}")
            return image_bytes  # Return original on error