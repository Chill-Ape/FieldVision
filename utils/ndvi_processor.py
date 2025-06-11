import numpy as np
from PIL import Image
import io
import logging
from shapely.geometry import Polygon, Point
import math

def process_ndvi_data(image_data, zones):
    """
    Process real NDVI image data and calculate average values for each zone
    
    Args:
        image_data: Raw image data from satellite API
        zones: Dictionary of zone polygons
    
    Returns:
        Dictionary with zone IDs as keys and NDVI values as values
    """
    try:
        if not image_data:
            logging.error("No image data provided for NDVI processing")
            return {}
            
        # If image_data is bytes, convert to PIL Image
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        else:
            image = image_data
        
        # Convert to numpy array for processing
        img_array = np.array(image)
        
        # Handle different image formats
        if len(img_array.shape) == 3:
            # For RGB images from Sentinel Hub, NDVI is typically in the red channel
            # or we need to convert the colorized NDVI back to values
            if img_array.shape[2] >= 3:
                # Extract NDVI from colorized image
                # Green areas typically have higher values
                green_channel = img_array[:, :, 1].astype(float)
                red_channel = img_array[:, :, 0].astype(float)
                
                # Convert RGB back to NDVI approximation
                # Higher green = higher NDVI, lower red = higher NDVI
                ndvi_array = (green_channel - red_channel) / (green_channel + red_channel + 1e-8)
                # Normalize to proper NDVI range
                ndvi_array = np.clip(ndvi_array, -1, 1)
            else:
                # Grayscale image
                ndvi_array = img_array[:, :, 0].astype(float) / 255.0 * 2 - 1
        else:
            # Already grayscale
            ndvi_array = img_array.astype(float)
            if ndvi_array.max() > 1:
                ndvi_array = ndvi_array / 255.0 * 2 - 1
        
        # Calculate NDVI values for each zone by sampling image regions
        zone_ndvi = {}
        image_height, image_width = ndvi_array.shape[:2]
        
        # Create a 3x3 grid mapping to image coordinates
        for zone_id in zones.keys():
            # Parse zone coordinates (zone_row_col format)
            parts = zone_id.split('_')
            if len(parts) == 3:
                row, col = int(parts[1]), int(parts[2])
                
                # Map zone to image region
                y_start = int((row / 3) * image_height)
                y_end = int(((row + 1) / 3) * image_height)
                x_start = int((col / 3) * image_width)
                x_end = int(((col + 1) / 3) * image_width)
                
                # Extract zone region and calculate mean NDVI
                zone_region = ndvi_array[y_start:y_end, x_start:x_end]
                
                if zone_region.size > 0:
                    # Remove any invalid values
                    valid_pixels = zone_region[np.isfinite(zone_region)]
                    if len(valid_pixels) > 0:
                        zone_mean = np.mean(valid_pixels)
                        zone_ndvi[zone_id] = round(float(zone_mean), 3)
                    else:
                        zone_ndvi[zone_id] = 0.0
                else:
                    zone_ndvi[zone_id] = 0.0
            else:
                # Fallback for malformed zone IDs
                zone_ndvi[zone_id] = round(float(np.mean(ndvi_array)), 3)
        
        logging.info(f"Processed real NDVI data for {len(zone_ndvi)} zones from satellite imagery")
        return zone_ndvi
        
    except Exception as e:
        logging.error(f"Error processing NDVI data: {str(e)}")
        return {}

def calculate_field_zones(coordinates):
    """
    Divide a field polygon into a 3x3 grid of zones
    
    Args:
        coordinates: List of [lat, lng] coordinate pairs
    
    Returns:
        Dictionary with zone IDs and their coordinate boundaries
    """
    try:
        if not coordinates or len(coordinates) < 3:
            raise ValueError("Invalid coordinates for zone calculation")
        
        # Find bounding box
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        
        # Calculate grid step size
        lat_step = (max_lat - min_lat) / 3
        lng_step = (max_lng - min_lng) / 3
        
        zones = {}
        
        # Create 3x3 grid
        for row in range(3):
            for col in range(3):
                zone_id = f"zone_{row}_{col}"
                
                # Calculate zone boundaries
                zone_min_lat = min_lat + (row * lat_step)
                zone_max_lat = min_lat + ((row + 1) * lat_step)
                zone_min_lng = min_lng + (col * lng_step)
                zone_max_lng = min_lng + ((col + 1) * lng_step)
                
                # Create zone polygon
                zone_coords = [
                    [zone_min_lat, zone_min_lng],
                    [zone_min_lat, zone_max_lng],
                    [zone_max_lat, zone_max_lng],
                    [zone_max_lat, zone_min_lng],
                    [zone_min_lat, zone_min_lng]  # Close the polygon
                ]
                
                zones[zone_id] = zone_coords
        
        logging.info(f"Created {len(zones)} zones for field analysis")
        return zones
        
    except Exception as e:
        logging.error(f"Error calculating field zones: {str(e)}")
        return {}

def calculate_ndvi_from_bands(red_band, nir_band):
    """
    Calculate NDVI from red and near-infrared bands
    NDVI = (NIR - Red) / (NIR + Red)
    
    Args:
        red_band: Red band image array
        nir_band: Near-infrared band image array
    
    Returns:
        NDVI array
    """
    try:
        # Avoid division by zero
        denominator = nir_band + red_band
        denominator = np.where(denominator == 0, 0.0001, denominator)
        
        ndvi = (nir_band - red_band) / denominator
        
        # Clip values to valid NDVI range
        ndvi = np.clip(ndvi, -1, 1)
        
        return ndvi
        
    except Exception as e:
        logging.error(f"Error calculating NDVI from bands: {str(e)}")
        return None

def analyze_vegetation_health(ndvi_value):
    """
    Analyze vegetation health based on NDVI value
    
    Args:
        ndvi_value: NDVI value (-1 to 1)
    
    Returns:
        Dictionary with health status and description
    """
    if ndvi_value > 0.6:
        return {
            'status': 'healthy',
            'description': 'Dense, healthy vegetation',
            'color': '#00ff00'
        }
    elif ndvi_value > 0.3:
        return {
            'status': 'moderate',
            'description': 'Moderate vegetation density',
            'color': '#ffff00'
        }
    elif ndvi_value > 0.1:
        return {
            'status': 'sparse',
            'description': 'Sparse vegetation or stressed crops',
            'color': '#ff8800'
        }
    else:
        return {
            'status': 'stressed',
            'description': 'Very stressed or no vegetation',
            'color': '#ff0000'
        }
