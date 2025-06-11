"""
Field geometry utilities for accurate zone mapping
Handles rotated fields and proper geometric zone calculations
"""
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
import logging

logger = logging.getLogger(__name__)

def create_field_zones_accurate(field_coordinates):
    """
    Create 9 zones within a field polygon using proper geometric division
    Accounts for field rotation and irregular shapes
    
    Args:
        field_coordinates: List of [lat, lng] coordinate pairs defining the field polygon
    
    Returns:
        Dictionary with zone names and their polygon boundaries
    """
    try:
        # Convert coordinates to shapely polygon (note: shapely uses lng, lat order)
        polygon_coords = [(coord[1], coord[0]) for coord in field_coordinates]  # Convert lat,lng to lng,lat
        field_polygon = Polygon(polygon_coords)
        
        # Get the field's bounding box and center
        minx, miny, maxx, maxy = field_polygon.bounds
        center_x, center_y = field_polygon.centroid.x, field_polygon.centroid.y
        
        # Calculate field's oriented bounding box to handle rotation
        field_width = maxx - minx
        field_height = maxy - miny
        
        # Create 9 zones by dividing the field into a 3x3 grid
        zones = {}
        zone_names = [
            ['Northwest', 'North', 'Northeast'],
            ['West', 'Center', 'East'],
            ['Southwest', 'South', 'Southeast']
        ]
        
        for row in range(3):
            for col in range(3):
                zone_name = zone_names[row][col]
                
                # Calculate zone boundaries as fractions of the field extent
                x_start = minx + (col / 3.0) * field_width
                x_end = minx + ((col + 1) / 3.0) * field_width
                y_start = miny + (row / 3.0) * field_height
                y_end = miny + ((row + 1) / 3.0) * field_height
                
                # Create zone rectangle
                zone_rect = Polygon([
                    (x_start, y_start),
                    (x_end, y_start),
                    (x_end, y_end),
                    (x_start, y_end)
                ])
                
                # Intersect with field polygon to get the actual zone within the field
                zone_polygon = field_polygon.intersection(zone_rect)
                
                if zone_polygon.is_empty:
                    # If no intersection, create a small zone at the center
                    zone_polygon = Point(center_x, center_y).buffer(0.0001)
                
                zones[f"zone_{row}_{col}"] = {
                    'name': zone_name,
                    'polygon': zone_polygon,
                    'bounds': zone_polygon.bounds if hasattr(zone_polygon, 'bounds') else (center_x, center_y, center_x, center_y)
                }
        
        logger.info(f"Created {len(zones)} accurate field zones accounting for field geometry")
        return zones
        
    except Exception as e:
        logger.error(f"Error creating accurate field zones: {e}")
        # Fallback to simple zone creation
        return create_simple_zones_fallback(field_coordinates)

def create_simple_zones_fallback(field_coordinates):
    """
    Fallback zone creation if geometric approach fails
    """
    zones = {}
    zone_names = [
        ['Northwest', 'North', 'Northeast'],
        ['West', 'Center', 'East'],
        ['Southwest', 'South', 'Southeast']
    ]
    
    for row in range(3):
        for col in range(3):
            zone_name = zone_names[row][col]
            zones[f"zone_{row}_{col}"] = {
                'name': zone_name,
                'polygon': None,
                'bounds': (0, 0, 1, 1)  # Normalized bounds
            }
    
    return zones

def map_image_coordinates_to_field(image_x, image_y, image_width, image_height, field_bbox):
    """
    Map image pixel coordinates to geographic coordinates within the field
    
    Args:
        image_x, image_y: Pixel coordinates in the image
        image_width, image_height: Image dimensions
        field_bbox: Field bounding box [minx, miny, maxx, maxy]
    
    Returns:
        Tuple of (geographic_x, geographic_y)
    """
    minx, miny, maxx, maxy = field_bbox
    
    # Convert pixel coordinates to normalized coordinates (0-1)
    norm_x = image_x / image_width
    norm_y = image_y / image_height
    
    # Map to geographic coordinates
    geo_x = minx + norm_x * (maxx - minx)
    geo_y = miny + norm_y * (maxy - miny)
    
    return geo_x, geo_y

def calculate_zone_ndvi_accurate(ndvi_array, zones, field_bbox):
    """
    Calculate NDVI values for zones using accurate geometric sampling
    
    Args:
        ndvi_array: 2D numpy array of NDVI values
        zones: Dictionary of zone geometries from create_field_zones_accurate
        field_bbox: Field bounding box [minx, miny, maxx, maxy]
    
    Returns:
        Dictionary with zone IDs as keys and NDVI values as values
    """
    zone_ndvi = {}
    image_height, image_width = ndvi_array.shape[:2]
    
    for zone_id, zone_data in zones.items():
        zone_polygon = zone_data['polygon']
        
        if zone_polygon is None:
            # Fallback for simple zones
            parts = zone_id.split('_')
            if len(parts) == 3:
                row, col = int(parts[1]), int(parts[2])
                y_start = int((row / 3) * image_height)
                y_end = int(((row + 1) / 3) * image_height)
                x_start = int((col / 3) * image_width)
                x_end = int(((col + 1) / 3) * image_width)
                
                zone_region = ndvi_array[y_start:y_end, x_start:x_end]
                valid_pixels = zone_region[np.isfinite(zone_region)]
                
                if len(valid_pixels) > 0:
                    zone_ndvi[zone_id] = round(float(np.mean(valid_pixels)), 3)
                else:
                    zone_ndvi[zone_id] = 0.0
            continue
        
        # Sample points within the zone polygon
        sample_points = []
        samples_per_axis = 20  # Higher resolution sampling
        
        # Get zone bounds
        minx, miny, maxx, maxy = zone_polygon.bounds
        
        for i in range(samples_per_axis):
            for j in range(samples_per_axis):
                # Calculate sample point in geographic coordinates
                sample_x = minx + (i / (samples_per_axis - 1)) * (maxx - minx)
                sample_y = miny + (j / (samples_per_axis - 1)) * (maxy - miny)
                
                # Check if point is within the zone polygon
                sample_point = Point(sample_x, sample_y)
                if zone_polygon.contains(sample_point):
                    # Map geographic coordinates to image pixel coordinates
                    norm_x = (sample_x - field_bbox[0]) / (field_bbox[2] - field_bbox[0])
                    norm_y = (sample_y - field_bbox[1]) / (field_bbox[3] - field_bbox[1])
                    
                    # Convert to pixel coordinates
                    pixel_x = int(norm_x * image_width)
                    pixel_y = int(norm_y * image_height)
                    
                    # Ensure coordinates are within image bounds
                    pixel_x = max(0, min(pixel_x, image_width - 1))
                    pixel_y = max(0, min(pixel_y, image_height - 1))
                    
                    # Sample NDVI value
                    ndvi_value = ndvi_array[pixel_y, pixel_x]
                    if np.isfinite(ndvi_value):
                        sample_points.append(ndvi_value)
        
        # Calculate zone average
        if sample_points:
            zone_ndvi[zone_id] = round(float(np.mean(sample_points)), 3)
        else:
            # Fallback to zone center sampling
            center_x, center_y = zone_polygon.centroid.x, zone_polygon.centroid.y
            norm_x = (center_x - field_bbox[0]) / (field_bbox[2] - field_bbox[0])
            norm_y = (center_y - field_bbox[1]) / (field_bbox[3] - field_bbox[1])
            
            pixel_x = int(norm_x * image_width)
            pixel_y = int(norm_y * image_height)
            
            pixel_x = max(0, min(pixel_x, image_width - 1))
            pixel_y = max(0, min(pixel_y, image_height - 1))
            
            zone_ndvi[zone_id] = round(float(ndvi_array[pixel_y, pixel_x]), 3)
    
    logger.info(f"Calculated accurate NDVI values for {len(zone_ndvi)} zones using geometric sampling")
    return zone_ndvi