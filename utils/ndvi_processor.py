import numpy as np
from PIL import Image
import io
import logging
from shapely.geometry import Polygon, Point
import math
from .field_geometry import create_field_zones_accurate, calculate_zone_ndvi_accurate

def process_ndvi_data(image_data, zones, field_coordinates=None, field_bbox=None):
    """
    Process real NDVI image data and calculate average values for each zone
    
    Args:
        image_data: Raw image data from satellite API
        zones: Dictionary of zone polygons
        field_coordinates: List of [lat, lng] coordinate pairs defining the field polygon
        field_bbox: Field bounding box [minx, miny, maxx, maxy] in geographic coordinates
    
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
        
        # Handle different image formats - Sentinel Hub returns colorized NDVI images
        if len(img_array.shape) == 3:
            # For colorized NDVI images from Sentinel Hub
            # Convert RGB color to NDVI values based on standard color mapping
            if img_array.shape[2] >= 3:
                r = img_array[:, :, 0].astype(float)
                g = img_array[:, :, 1].astype(float) 
                b = img_array[:, :, 2].astype(float)
                
                # Improved color-to-NDVI mapping for accurate interpretation
                # Based on standard NDVI visualization: Red=Poor, Yellow=Moderate, Green=Good
                
                # Calculate color dominance for accurate classification
                total_intensity = r + g + b + 1e-6  # Avoid division by zero
                r_ratio = r / total_intensity
                g_ratio = g / total_intensity
                b_ratio = b / total_intensity
                
                # Create NDVI array based on precise color analysis
                ndvi_array = np.zeros_like(r, dtype=np.float32)
                
                # Bright green areas (healthy vegetation) - high green dominance
                bright_green_mask = (g > 180) & (g > r + 50) & (g > b + 50)
                ndvi_array[bright_green_mask] = 0.6 + (g[bright_green_mask] - 180) / 75.0 * 0.2  # 0.6 to 0.8
                
                # Medium green areas (good vegetation) - moderate green dominance
                medium_green_mask = (g > 120) & (g > r + 20) & (g > b + 20) & (~bright_green_mask)
                ndvi_array[medium_green_mask] = 0.4 + (g[medium_green_mask] - 120) / 60.0 * 0.2  # 0.4 to 0.6
                
                # Yellow-green areas (moderate vegetation) - mixed green and red
                yellow_mask = (g > 100) & (r > 80) & (abs(g - r) < 50) & (~bright_green_mask) & (~medium_green_mask)
                ndvi_array[yellow_mask] = 0.2 + (g[yellow_mask] - 100) / 100.0 * 0.2  # 0.2 to 0.4
                
                # Orange areas (stressed vegetation) - more red than green
                orange_mask = (r > g) & (r > 100) & (g > 50) & (~yellow_mask)
                ndvi_array[orange_mask] = 0.1 + (g[orange_mask] / 255.0) * 0.1  # 0.1 to 0.2
                
                # Red areas (poor/bare soil) - high red dominance
                red_mask = (r > g + 30) & (r > b + 30) & (r > 80)
                ndvi_array[red_mask] = -0.1 + (g[red_mask] / 255.0) * 0.2  # -0.1 to 0.1
                
                # Very dark red areas (very poor conditions)
                dark_red_mask = (r > g + 20) & (r > b + 20) & (r > 50) & (r <= 80)
                ndvi_array[dark_red_mask] = -0.2 + (g[dark_red_mask] / 255.0) * 0.1  # -0.2 to -0.1
                
                # Blue/water areas (negative NDVI)
                water_mask = (b > r) & (b > g) & (b > 100)
                ndvi_array[water_mask] = -0.3 + (b[water_mask] / 255.0) * 0.1  # -0.3 to -0.2
                
                # Very dark areas (shadows or bare soil)
                dark_mask = (r + g + b < 100) & (~water_mask)
                ndvi_array[dark_mask] = -0.1
                
                # Fill any remaining pixels with basic color ratio
                unassigned_mask = (ndvi_array == 0) & (~bright_green_mask) & (~medium_green_mask) & (~yellow_mask) & (~orange_mask) & (~red_mask) & (~dark_red_mask) & (~water_mask) & (~dark_mask)
                if np.any(unassigned_mask):
                    # Use green-red ratio for unassigned pixels
                    color_ratio = (g[unassigned_mask] - r[unassigned_mask]) / (g[unassigned_mask] + r[unassigned_mask] + 1e-6)
                    ndvi_array[unassigned_mask] = color_ratio * 0.4 + 0.2
                
                # Ensure values are in valid NDVI range
                ndvi_array = np.clip(ndvi_array, -1.0, 1.0)
                
                logging.info(f"NDVI color analysis - Red pixels: {np.sum(red_mask)}, Green pixels: {np.sum(bright_green_mask + medium_green_mask)}, Yellow pixels: {np.sum(yellow_mask)}")
            else:
                # Grayscale image - convert to NDVI range
                ndvi_array = (img_array[:, :, 0].astype(float) / 255.0) * 1.6 - 0.3  # Map to typical NDVI range
        else:
            # Already grayscale - convert to NDVI range
            ndvi_array = (img_array.astype(float) / 255.0) * 1.6 - 0.3
        
        # Use accurate geometric zone mapping if field coordinates are available
        if field_coordinates and field_bbox:
            try:
                # Create accurate field zones accounting for rotation and geometry
                accurate_zones = create_field_zones_accurate(field_coordinates)
                zone_ndvi = calculate_zone_ndvi_accurate(ndvi_array, accurate_zones, field_bbox)
                logging.info("Using accurate geometric zone mapping for NDVI calculations")
            except Exception as e:
                logging.warning(f"Geometric zone mapping failed, using fallback: {e}")
                zone_ndvi = None
        else:
            zone_ndvi = None
        
        # Fallback to enhanced grid-based sampling if geometric mapping unavailable
        if zone_ndvi is None:
            zone_ndvi = {}
            image_height, image_width = ndvi_array.shape[:2]
            
            for zone_id in zones.keys():
                parts = zone_id.split('_')
                if len(parts) == 3:
                    row, col = int(parts[1]), int(parts[2])
                    
                    # Enhanced sampling with higher resolution for better accuracy
                    sample_points = []
                    samples_per_axis = 15  # Increased sampling density
                    
                    for i in range(samples_per_axis):
                        for j in range(samples_per_axis):
                            zone_y = (row + i / samples_per_axis) / 3
                            zone_x = (col + j / samples_per_axis) / 3
                            
                            img_y = int(zone_y * image_height)
                            img_x = int(zone_x * image_width)
                            
                            img_y = max(0, min(img_y, image_height - 1))
                            img_x = max(0, min(img_x, image_width - 1))
                            
                            if np.isfinite(ndvi_array[img_y, img_x]):
                                sample_points.append(ndvi_array[img_y, img_x])
                    
                    if sample_points:
                        zone_ndvi[zone_id] = round(float(np.mean(sample_points)), 3)
                    else:
                        zone_ndvi[zone_id] = 0.0
                else:
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
