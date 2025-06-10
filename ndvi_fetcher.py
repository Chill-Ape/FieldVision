"""
NDVI fetcher module for Sentinel Hub API
Handles NDVI image requests and processing
"""

import requests
import logging
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
    
    def create_request_payload(self, bbox: List[float], width: int = 2500, height: int = 2500) -> dict:
        """
        Create the request payload for Sentinel Hub Process API
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat]
            width: Output image width in pixels
            height: Output image height in pixels
            
        Returns:
            Dictionary containing the complete request payload
        """
        # Calculate time range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
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
    
    def fetch_ndvi_image(self, bbox: List[float], width: int = 2500, height: int = 2500) -> Optional[bytes]:
        """
        Fetch NDVI image for the given bounding box at maximum resolution
        
        Args:
            bbox: Bounding box coordinates [min_lng, min_lat, max_lng, max_lat] in EPSG:4326
            width: Output image width in pixels (default 2500 for max detail)
            height: Output image height in pixels (default 2500 for max detail)
            
        Returns:
            PNG image bytes or None if request fails
        """
        # Get access token
        token = self.auth.get_access_token()
        if not token:
            logger.error("Failed to obtain access token")
            return None
        
        # Create request payload
        payload = self.create_request_payload(bbox, width, height)
        
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