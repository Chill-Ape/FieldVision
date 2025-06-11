"""
Enhanced NDVI Analyzer for FieldVision AI
Processes satellite imagery and generates agricultural insights
"""

import numpy as np
from PIL import Image
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class NDVIAnalyzer:
    """
    Advanced NDVI analysis with zone-based processing for agricultural insights
    """
    
    def __init__(self):
        """Initialize the NDVI analyzer with agricultural parameters"""
        self.zone_grid_size = (3, 3)  # 3x3 grid for zone analysis
        
        # NDVI classification thresholds
        self.ndvi_thresholds = {
            'excellent': 0.7,
            'good': 0.5,
            'fair': 0.3,
            'poor': 0.1,
            'critical': 0.0
        }
    
    def analyze_ndvi_image(self, image_bytes: bytes, field_geometry: Optional[Dict] = None) -> Dict:
        """
        Analyze NDVI image and extract zone-based vegetation health metrics
        
        Args:
            image_bytes: Raw NDVI image data
            field_geometry: GeoJSON geometry for field boundaries
            
        Returns:
            Dictionary with zone analysis and health metrics
        """
        try:
            # Load and process the NDVI image
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if needed for analysis
            if image.mode == 'RGBA':
                # Create a white background for transparent areas
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array for analysis
            img_array = np.array(image)
            
            # Extract NDVI values from the color-coded image
            ndvi_values = self._extract_ndvi_from_colors(img_array)
            
            # Divide field into analysis zones
            zones = self._create_analysis_zones(ndvi_values)
            
            # Calculate zone statistics
            zone_stats = {}
            for zone_id, zone_data in zones.items():
                zone_stats[zone_id] = self._calculate_zone_statistics(zone_data)
            
            # Generate overall field statistics
            field_stats = self._calculate_field_statistics(ndvi_values, zone_stats)
            
            # Create visualization data
            visualization_data = self._create_visualization_data(zones, zone_stats)
            
            return {
                'zone_statistics': zone_stats,
                'field_statistics': field_stats,
                'visualization_data': visualization_data,
                'analysis_metadata': {
                    'image_size': image.size,
                    'total_pixels': img_array.size,
                    'zones_analyzed': len(zones),
                    'analysis_timestamp': f"{np.datetime64('now')}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing NDVI image: {e}")
            raise
    
    def _extract_ndvi_from_colors(self, img_array: np.ndarray) -> np.ndarray:
        """
        Extract NDVI values from color-coded satellite image
        
        NDVI images typically use color mapping:
        - Red/Brown: Low NDVI (0.0-0.3) - bare soil, stressed vegetation
        - Yellow/Orange: Medium NDVI (0.3-0.5) - moderate vegetation
        - Light Green: Good NDVI (0.5-0.7) - healthy vegetation
        - Dark Green: Excellent NDVI (0.7-1.0) - very healthy vegetation
        """
        # Normalize RGB values to 0-1
        r = img_array[:, :, 0].astype(float) / 255.0
        g = img_array[:, :, 1].astype(float) / 255.0
        b = img_array[:, :, 2].astype(float) / 255.0
        
        # Calculate NDVI approximation based on color analysis
        # This is a simplified approach - in real scenarios, you'd have direct NDVI values
        
        # Green dominance indicates higher NDVI
        green_strength = g - np.maximum(r, b)
        
        # Red dominance indicates lower NDVI (stress)
        red_strength = r - np.maximum(g, b)
        
        # Calculate estimated NDVI values
        ndvi_estimated = np.zeros_like(r)
        
        # Very green areas (high NDVI)
        green_mask = (g > 0.6) & (g > r) & (g > b)
        ndvi_estimated[green_mask] = 0.5 + (g[green_mask] - 0.6) * 1.25  # Scale to 0.5-1.0
        
        # Moderate green areas
        moderate_green = (g > 0.4) & (g > r) & (g > b) & ~green_mask
        ndvi_estimated[moderate_green] = 0.3 + (g[moderate_green] - 0.4) * 1.0  # Scale to 0.3-0.5
        
        # Red/brown areas (low NDVI)
        red_mask = (r > g) & (r > b)
        ndvi_estimated[red_mask] = np.maximum(0, 0.3 - red_strength[red_mask] * 0.5)
        
        # Yellow/orange areas (medium NDVI)
        yellow_mask = (r + g > 1.2) & (b < 0.5) & ~red_mask & ~green_mask
        ndvi_estimated[yellow_mask] = 0.2 + (g[yellow_mask] - r[yellow_mask] + 1) * 0.15
        
        # Ensure values are within valid NDVI range
        ndvi_estimated = np.clip(ndvi_estimated, 0.0, 1.0)
        
        return ndvi_estimated
    
    def _create_analysis_zones(self, ndvi_values: np.ndarray) -> Dict[str, np.ndarray]:
        """Divide the field into analysis zones for targeted recommendations"""
        zones = {}
        height, width = ndvi_values.shape
        
        # Calculate zone dimensions
        zone_height = height // self.zone_grid_size[0]
        zone_width = width // self.zone_grid_size[1]
        
        for row in range(self.zone_grid_size[0]):
            for col in range(self.zone_grid_size[1]):
                zone_id = f"zone_{row}_{col}"
                
                # Calculate zone boundaries
                start_row = row * zone_height
                end_row = (row + 1) * zone_height if row < self.zone_grid_size[0] - 1 else height
                start_col = col * zone_width
                end_col = (col + 1) * zone_width if col < self.zone_grid_size[1] - 1 else width
                
                # Extract zone data
                zone_data = ndvi_values[start_row:end_row, start_col:end_col]
                zones[zone_id] = zone_data
        
        return zones
    
    def _calculate_zone_statistics(self, zone_data: np.ndarray) -> Dict:
        """Calculate comprehensive statistics for a field zone"""
        # Remove any invalid values (NaN, inf)
        valid_data = zone_data[np.isfinite(zone_data)]
        
        if len(valid_data) == 0:
            return {
                'mean_ndvi': 0.0,
                'median_ndvi': 0.0,
                'std_ndvi': 0.0,
                'min_ndvi': 0.0,
                'max_ndvi': 0.0,
                'health_classification': 'unknown',
                'vegetation_cover': 0.0,
                'stress_percentage': 100.0,
                'pixel_count': 0
            }
        
        # Basic statistics
        mean_ndvi = float(np.mean(valid_data))
        median_ndvi = float(np.median(valid_data))
        std_ndvi = float(np.std(valid_data))
        min_ndvi = float(np.min(valid_data))
        max_ndvi = float(np.max(valid_data))
        
        # Health classification
        health_classification = self._classify_vegetation_health(mean_ndvi)
        
        # Vegetation coverage (percentage of pixels with NDVI > 0.2)
        vegetation_pixels = np.sum(valid_data > 0.2)
        vegetation_cover = (vegetation_pixels / len(valid_data)) * 100
        
        # Stress percentage (pixels with NDVI < 0.3)
        stress_pixels = np.sum(valid_data < 0.3)
        stress_percentage = (stress_pixels / len(valid_data)) * 100
        
        return {
            'mean_ndvi': round(mean_ndvi, 3),
            'median_ndvi': round(median_ndvi, 3),
            'std_ndvi': round(std_ndvi, 3),
            'min_ndvi': round(min_ndvi, 3),
            'max_ndvi': round(max_ndvi, 3),
            'health_classification': health_classification,
            'vegetation_cover': round(vegetation_cover, 1),
            'stress_percentage': round(stress_percentage, 1),
            'pixel_count': len(valid_data)
        }
    
    def _calculate_field_statistics(self, ndvi_values: np.ndarray, zone_stats: Dict) -> Dict:
        """Calculate overall field statistics"""
        # Overall field NDVI statistics
        valid_ndvi = ndvi_values[np.isfinite(ndvi_values)]
        
        if len(valid_ndvi) == 0:
            return {
                'overall_health': 'unknown',
                'field_mean_ndvi': 0.0,
                'field_uniformity': 0.0,
                'healthy_zones': 0,
                'stressed_zones': 0,
                'total_zones': len(zone_stats)
            }
        
        field_mean = float(np.mean(valid_ndvi))
        field_std = float(np.std(valid_ndvi))
        
        # Field uniformity (lower std = more uniform)
        field_uniformity = max(0, 100 - (field_std * 200))  # Convert to percentage
        
        # Count zone health status
        healthy_zones = sum(1 for stats in zone_stats.values() 
                           if stats['mean_ndvi'] > 0.5)
        stressed_zones = sum(1 for stats in zone_stats.values() 
                            if stats['mean_ndvi'] < 0.3)
        
        # Overall health assessment
        overall_health = self._classify_vegetation_health(field_mean)
        
        return {
            'overall_health': overall_health,
            'field_mean_ndvi': round(field_mean, 3),
            'field_uniformity': round(field_uniformity, 1),
            'healthy_zones': healthy_zones,
            'stressed_zones': stressed_zones,
            'total_zones': len(zone_stats),
            'zone_health_distribution': self._calculate_health_distribution(zone_stats)
        }
    
    def _classify_vegetation_health(self, ndvi_value: float) -> str:
        """Classify vegetation health based on NDVI value"""
        if ndvi_value >= self.ndvi_thresholds['excellent']:
            return 'excellent'
        elif ndvi_value >= self.ndvi_thresholds['good']:
            return 'good'
        elif ndvi_value >= self.ndvi_thresholds['fair']:
            return 'fair'
        elif ndvi_value >= self.ndvi_thresholds['poor']:
            return 'poor'
        else:
            return 'critical'
    
    def _calculate_health_distribution(self, zone_stats: Dict) -> Dict:
        """Calculate distribution of health classifications across zones"""
        distribution = {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0, 'critical': 0}
        
        for stats in zone_stats.values():
            classification = stats['health_classification']
            distribution[classification] += 1
        
        # Convert to percentages
        total_zones = len(zone_stats)
        if total_zones > 0:
            for key in distribution:
                distribution[key] = round((distribution[key] / total_zones) * 100, 1)
        
        return distribution
    
    def _create_visualization_data(self, zones: Dict, zone_stats: Dict) -> Dict:
        """Create data for visualization components"""
        # Color mapping for health status
        health_colors = {
            'excellent': '#2d5a3d',  # Dark green
            'good': '#4a7c59',       # Medium green
            'fair': '#8fbc8f',       # Light green
            'poor': '#daa520',       # Gold/yellow
            'critical': '#dc143c'     # Red
        }
        
        # Zone visualization data
        zone_viz = {}
        for zone_id, stats in zone_stats.items():
            zone_viz[zone_id] = {
                'color': health_colors.get(stats['health_classification'], '#808080'),
                'ndvi': stats['mean_ndvi'],
                'health': stats['health_classification'],
                'coverage': stats['vegetation_cover']
            }
        
        return {
            'zone_colors': zone_viz,
            'health_colors': health_colors,
            'ndvi_scale': {
                'min': 0.0,
                'max': 1.0,
                'optimal_range': [0.5, 0.8]
            }
        }

# Convenience functions for integration
def analyze_field_ndvi(image_bytes: bytes, field_geometry: Optional[Dict] = None) -> Dict:
    """
    Main entry point for NDVI analysis
    
    Args:
        image_bytes: NDVI image data
        field_geometry: Optional field boundary geometry
        
    Returns:
        Complete NDVI analysis results
    """
    analyzer = NDVIAnalyzer()
    return analyzer.analyze_ndvi_image(image_bytes, field_geometry)

def get_zone_ndvi_values(analysis_results: Dict) -> Dict[str, float]:
    """
    Extract zone NDVI values for recommendation engine
    
    Args:
        analysis_results: Results from analyze_field_ndvi
        
    Returns:
        Dictionary mapping zone IDs to mean NDVI values
    """
    zone_stats = analysis_results.get('zone_statistics', {})
    return {zone_id: stats['mean_ndvi'] for zone_id, stats in zone_stats.items()}