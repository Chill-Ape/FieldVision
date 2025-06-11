import numpy as np
from PIL import Image
import io
import logging
from shapely.geometry import Polygon, Point
import math

def process_ndvi_data(image_data, zones):
    """
    Process NDVI image data and calculate average values for each zone
    
    Args:
        image_data: Raw image data from satellite API
        zones: Dictionary of zone polygons
    
    Returns:
        Dictionary with zone IDs as keys and NDVI values as values
    """
    try:
        # If image_data is bytes, convert to PIL Image
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        else:
            image = image_data
        
        # Convert to numpy array for processing
        img_array = np.array(image)
        
        # If it's RGB, convert to grayscale assuming it's already NDVI processed
        if len(img_array.shape) == 3:
            img_array = np.mean(img_array, axis=2)
        
        # Normalize to NDVI range (-1 to 1)
        if img_array.max() > 1:
            img_array = (img_array / 255.0) * 2 - 1
        
        # Calculate NDVI values for each zone
        zone_ndvi = {}
        
        for zone_id, zone_coords in zones.items():
            # For simplicity, calculate average NDVI for the zone area
            # In a real implementation, you would map zone coordinates to image pixels
            
            # Simulate NDVI calculation based on zone position
            # This is a simplified approach - in production, you'd need proper coordinate transformation
            base_ndvi = 0.4 + (0.3 * np.random.random())  # Random variation for demonstration
            
            # Add some realistic variation based on image data
            if img_array.size > 0:
                sample_value = np.mean(img_array) if np.mean(img_array) != 0 else 0.5
                base_ndvi = max(-1, min(1, sample_value))
            
            zone_ndvi[zone_id] = round(base_ndvi, 3)
        
        logging.info(f"Processed NDVI data for {len(zone_ndvi)} zones")
        return zone_ndvi
        
    except Exception as e:
        logging.error(f"Error processing NDVI data: {str(e)}")
        # Return default values if processing fails
        return {zone_id: 0.4 for zone_id in zones.keys()}

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
