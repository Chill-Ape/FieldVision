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
    
    // Store original NDVI for debugging and apply adaptive contrast enhancement
    let originalNdvi = ndvi;
    
    // Apply adaptive histogram equalization for agricultural areas
    // Focus on the typical crop range (0.2-0.9) and stretch it to full color range
    if (ndvi >= 0.2 && ndvi <= 0.9) {
        // Normalize to 0-1 range within agricultural bounds
        let normalized = (ndvi - 0.2) / 0.7;
        
        // Apply sigmoid stretch for better visual separation
        let sigmoid = 1 / (1 + Math.exp(-8 * (normalized - 0.5)));
        
        // Map back to expanded NDVI range for better color separation
        ndvi = 0.2 + sigmoid * 0.7;
    }
    
    // Add small random variation to prevent uniform areas (only for visualization)
    if (ndvi > 0.4) {
        let variation = (Math.random() - 0.5) * 0.05; // ±2.5% variation
        ndvi = Math.max(0.2, Math.min(0.9, ndvi + variation));
    }
    
    // Fine-grained NDVI color mapping with maximum agricultural detail
    if (ndvi < -0.3) return [0.1, 0.1, 0.3]; // Deep water - navy blue
    if (ndvi < -0.1) return [0.3, 0.3, 0.5]; // Shallow water - blue
    if (ndvi < 0.05) return [0.7, 0.6, 0.4]; // Bare soil/sand - tan
    if (ndvi < 0.1) return [0.9, 0.1, 0.1]; // Critical stress - bright red
    if (ndvi < 0.15) return [0.9, 0.3, 0.1]; // Severe stress - red-orange
    if (ndvi < 0.2) return [0.9, 0.5, 0.1]; // High stress - orange
    if (ndvi < 0.25) return [0.9, 0.7, 0.1]; // Moderate stress - orange-yellow
    if (ndvi < 0.3) return [0.9, 0.9, 0.1]; // Mild stress - yellow
    if (ndvi < 0.35) return [0.7, 0.9, 0.2]; // Early recovery - yellow-green
    if (ndvi < 0.4) return [0.5, 0.9, 0.3]; // Fair vigor - light green
    if (ndvi < 0.42) return [0.4, 0.8, 0.2]; // Below average - medium light green
    if (ndvi < 0.44) return [0.3, 0.75, 0.15]; // Average vigor - medium green
    if (ndvi < 0.46) return [0.25, 0.7, 0.1]; // Above average - green
    if (ndvi < 0.48) return [0.2, 0.65, 0.08]; // Good vigor - darker green
    if (ndvi < 0.5) return [0.15, 0.6, 0.06]; // Very good - dark green
    if (ndvi < 0.52) return [0.12, 0.55, 0.05]; // High vigor - very dark green
    if (ndvi < 0.54) return [0.1, 0.5, 0.04]; // Superior vigor - deep green
    if (ndvi < 0.56) return [0.08, 0.45, 0.03]; // Excellent vigor - deeper green
    if (ndvi < 0.58) return [0.06, 0.4, 0.02]; // Outstanding vigor - very deep green
    if (ndvi < 0.6) return [0.04, 0.35, 0.01]; // Peak vigor - deepest green
    return [0.02, 0.3, 0.0]; // Maximum vigor - forest green
}
"""
    
    def create_request_payload(self, bbox: List[float], width: int = 2500, height: int = 2500, days_back: int = 10) -> dict:
        """
        Create the request payload for Sentinel Hub Process API
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            width: Output image width in pixels
            height: Output image height in pixels
            days_back: Number of days to look back for imagery
            
        Returns:
            Dictionary containing the complete request payload
        """
        # Calculate time range - prioritize most recent imagery
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        return {
            "input": {
                "bounds": {
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
                        "maxCloudCoverage": 10
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
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'image/png'
        }
        
        # Try progressively longer time windows to find the freshest available imagery
        time_windows = [7, 14, 21, 30]  # Start with 7 days, expand if needed
        
        for days_back in time_windows:
            payload = self.create_request_payload(bbox, width, height, days_back)
            
            try:
                logger.info(f"Requesting NDVI image for bbox: {bbox} (last {days_back} days)")
                response = requests.post(
                    self.process_url,
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully fetched NDVI image from last {days_back} days ({len(response.content)} bytes)")
                    
                    # Apply polygon masking if geometry is provided
                    if geometry:
                        return self._apply_polygon_mask(response.content, bbox, geometry, width, height)
                    
                    return response.content
                elif response.status_code == 400:
                    # Check if it's a "no data" error - try longer time window
                    try:
                        error_response = response.json()
                        if 'no data' in str(error_response).lower() or 'temporal' in str(error_response).lower():
                            logger.warning(f"No satellite data available in last {days_back} days, trying longer window...")
                            continue  # Try next time window
                    except:
                        pass
                    
                    logger.error(f"API request failed with status {response.status_code}: {response.text}")
                    continue
                else:
                    logger.error(f"Failed to fetch NDVI image: {response.status_code} - {response.text}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching NDVI image: {e}")
                continue
        
        # If we've exhausted all time windows without success
        logger.error("Failed to fetch NDVI image from any time window")
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