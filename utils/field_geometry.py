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
    Create 9 zones within a field polygon using the field's actual orientation
    Divides the field along its major and minor axes for accurate zone mapping
    
    Args:
        field_coordinates: List of [lat, lng] coordinate pairs defining the field polygon
    
    Returns:
        Dictionary with zone names and their polygon boundaries
    """
    try:
        # Convert coordinates to shapely polygon (note: shapely uses lng, lat order)
        polygon_coords = [(coord[1], coord[0]) for coord in field_coordinates]  # Convert lat,lng to lng,lat
        field_polygon = Polygon(polygon_coords)
        
        # Get the field's vertices to understand its actual shape
        vertices = list(field_polygon.exterior.coords[:-1])  # Remove duplicate last point
        
        # Find the field's oriented bounding box by calculating the minimum area rectangle
        # This gives us the field's natural orientation
        field_bounds = field_polygon.bounds
        minx, miny, maxx, maxy = field_bounds
        
        # Calculate the field's principal axes by analyzing vertex distribution
        # Find the longest edge to determine field orientation
        max_dist = 0
        primary_vector = None
        
        for i in range(len(vertices)):
            for j in range(i + 2, len(vertices)):  # Skip adjacent vertices
                v1, v2 = vertices[i], vertices[j]
                dist = ((v2[0] - v1[0])**2 + (v2[1] - v1[1])**2)**0.5
                if dist > max_dist:
                    max_dist = dist
                    primary_vector = (v2[0] - v1[0], v2[1] - v1[1])
        
        # Normalize the primary vector
        if primary_vector:
            length = (primary_vector[0]**2 + primary_vector[1]**2)**0.5
            if length > 0:
                primary_unit = (primary_vector[0] / length, primary_vector[1] / length)
                # Perpendicular vector
                secondary_unit = (-primary_unit[1], primary_unit[0])
            else:
                primary_unit = (1, 0)
                secondary_unit = (0, 1)
        else:
            primary_unit = (1, 0)
            secondary_unit = (0, 1)
        
        # Get field centroid
        centroid = field_polygon.centroid
        cx, cy = centroid.x, centroid.y
        
        # Create zones by dividing the field along its natural axes
        zones = {}
        zone_names = [
            ['Northwest', 'North', 'Northeast'],
            ['West', 'Center', 'East'],
            ['Southwest', 'South', 'Southeast']
        ]
        
        # Calculate the field's extent along its primary axes
        # Project all vertices onto the primary and secondary axes
        primary_projections = []
        secondary_projections = []
        
        for vertex in vertices:
            # Vector from centroid to vertex
            v = (vertex[0] - cx, vertex[1] - cy)
            # Project onto primary and secondary axes
            primary_proj = v[0] * primary_unit[0] + v[1] * primary_unit[1]
            secondary_proj = v[0] * secondary_unit[0] + v[1] * secondary_unit[1]
            primary_projections.append(primary_proj)
            secondary_projections.append(secondary_proj)
        
        # Get the range of projections
        primary_min, primary_max = min(primary_projections), max(primary_projections)
        secondary_min, secondary_max = min(secondary_projections), max(secondary_projections)
        
        # Create 3x3 grid of zones aligned with field orientation
        for row in range(3):
            for col in range(3):
                zone_name = zone_names[row][col]
                
                # Calculate zone boundaries along field axes
                primary_start = primary_min + (col / 3.0) * (primary_max - primary_min)
                primary_end = primary_min + ((col + 1) / 3.0) * (primary_max - primary_min)
                secondary_start = secondary_min + (row / 3.0) * (secondary_max - secondary_min)
                secondary_end = secondary_min + ((row + 1) / 3.0) * (secondary_max - secondary_min)
                
                # Convert back to geographic coordinates
                # Zone corners in local coordinate system
                corners_local = [
                    (primary_start, secondary_start),
                    (primary_end, secondary_start),
                    (primary_end, secondary_end),
                    (primary_start, secondary_end)
                ]
                
                # Convert to global coordinates
                corners_global = []
                for p_proj, s_proj in corners_local:
                    global_x = cx + p_proj * primary_unit[0] + s_proj * secondary_unit[0]
                    global_y = cy + p_proj * primary_unit[1] + s_proj * secondary_unit[1]
                    corners_global.append((global_x, global_y))
                
                # Create zone polygon and intersect with field
                zone_rect = Polygon(corners_global)
                zone_polygon = field_polygon.intersection(zone_rect)
                
                if zone_polygon.is_empty or zone_polygon.area < 1e-10:
                    # Create a small zone at the expected location
                    zone_center_x = cx + ((primary_start + primary_end) / 2) * primary_unit[0] + ((secondary_start + secondary_end) / 2) * secondary_unit[0]
                    zone_center_y = cy + ((primary_start + primary_end) / 2) * primary_unit[1] + ((secondary_start + secondary_end) / 2) * secondary_unit[1]
                    zone_polygon = Point(zone_center_x, zone_center_y).buffer(0.0001)
                
                zones[f"zone_{row}_{col}"] = {
                    'name': zone_name,
                    'polygon': zone_polygon,
                    'bounds': zone_polygon.bounds if hasattr(zone_polygon, 'bounds') else (cx, cy, cx, cy)
                }
        
        logger.info(f"Created {len(zones)} orientation-aware field zones using field's natural axes")
        return zones
        
    except Exception as e:
        logger.error(f"Error creating orientation-aware field zones: {e}")
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
                    
                    # Convert to pixel coordinates (invert Y axis for image coordinates)
                    pixel_x = int(norm_x * image_width)
                    pixel_y = int((1.0 - norm_y) * image_height)  # Flip Y-axis
                    
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