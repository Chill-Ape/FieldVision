import logging
from datetime import datetime

def get_zone_ndvi_values(analysis_results):
    """
    Extract zone NDVI values for recommendation engine
    
    Args:
        analysis_results: Results from analyze_field_ndvi
        
    Returns:
        Dictionary mapping zone IDs to mean NDVI values
    """
    try:
        zone_ndvi_values = {}
        
        if not analysis_results or 'zone_stats' not in analysis_results:
            return {}
        
        zone_stats = analysis_results['zone_stats']
        
        for zone_id, stats in zone_stats.items():
            if isinstance(stats, dict) and 'mean_ndvi' in stats:
                zone_ndvi_values[zone_id] = stats['mean_ndvi']
            elif isinstance(stats, (int, float)):
                zone_ndvi_values[zone_id] = stats
        
        return zone_ndvi_values
        
    except Exception as e:
        logging.error(f"Error extracting zone NDVI values: {str(e)}")
        return {}

def generate_recommendations(ndvi_data, zones):
    """
    Generate AI-powered recommendations based on real NDVI data and zone analysis
    
    Args:
        ndvi_data: Dictionary with zone IDs and NDVI values
        zones: Dictionary with zone information
    
    Returns:
        List of recommendation dictionaries
    """
    try:
        recommendations = []
        
        if not ndvi_data or not isinstance(ndvi_data, dict):
            logging.error("Invalid or missing NDVI data for recommendations")
            return []
        
        # Filter out any invalid NDVI values
        valid_ndvi_data = {k: v for k, v in ndvi_data.items() 
                          if isinstance(v, (int, float)) and -1 <= v <= 1}
        
        if not valid_ndvi_data:
            logging.error("No valid NDVI values found for recommendations")
            return []
        
        # Analyze each zone with valid data
        for zone_id, ndvi_value in valid_ndvi_data.items():
            zone_recommendations = analyze_zone_health(zone_id, ndvi_value)
            recommendations.extend(zone_recommendations)
        
        # Add overall field recommendations based on real data
        overall_recommendations = analyze_overall_field_health(valid_ndvi_data)
        recommendations.extend(overall_recommendations)
        
        # Sort recommendations by priority (1 = highest, 5 = lowest)
        recommendations.sort(key=lambda x: x.get('priority', 5))
        
        # Limit to top 5 most important recommendations
        recommendations = recommendations[:5]
        
        logging.info(f"Generated {len(recommendations)} recommendations from real NDVI data")
        return recommendations
        
    except Exception as e:
        logging.error(f"Error generating recommendations: {str(e)}")
        return []

def analyze_zone_health(zone_id, ndvi_value):
    """
    Analyze individual zone health and generate specific recommendations
    
    Args:
        zone_id: Zone identifier (e.g., "zone_0_1")
        ndvi_value: NDVI value for the zone
    
    Returns:
        List of recommendations for this zone
    """
    recommendations = []
    
    # Parse zone position for directional recommendations
    zone_parts = zone_id.split('_')
    if len(zone_parts) == 3:
        row, col = int(zone_parts[1]), int(zone_parts[2])
        zone_name = get_zone_name(row, col)
    else:
        zone_name = zone_id
    
    # Only generate recommendations for zones that need attention
    # Don't spam with too many recommendations
    if ndvi_value < 0.2:
        recommendations.append({
            "type": "critical",
            "zone": zone_name,
            "message": f"Critical vegetation stress in {zone_name}. Immediate action required.",
            "priority": 1,
            "actions": [
                "Emergency irrigation needed",
                "Soil testing recommended",
                "Check for pest damage"
            ]
        })
    elif ndvi_value < 0.35:
        recommendations.append({
            "type": "warning",
            "zone": zone_name,
            "message": f"Below-average vegetation health in {zone_name}.",
            "priority": 2,
            "actions": [
                "Increase watering schedule",
                "Monitor for disease signs",
                "Consider fertilizer application"
            ]
        })
    elif ndvi_value > 0.75:
        # Only show success for exceptionally healthy zones
        recommendations.append({
            "type": "success",
            "zone": zone_name,
            "message": f"Excellent vegetation health in {zone_name}.",
            "priority": 4,
            "actions": [
                "Maintain current practices"
            ]
        })
    
    return recommendations

def analyze_overall_field_health(ndvi_data):
    """
    Analyze overall field health and generate field-wide recommendations
    
    Args:
        ndvi_data: Dictionary with all zone NDVI values
    
    Returns:
        List of field-wide recommendations
    """
    recommendations = []
    
    if not ndvi_data:
        return recommendations
    
    values = list(ndvi_data.values())
    avg_ndvi = sum(values) / len(values)
    min_ndvi = min(values)
    max_ndvi = max(values)
    ndvi_variance = calculate_variance(values)
    
    # Count problem zones to avoid redundant recommendations
    critical_zones = sum(1 for v in values if v < 0.2)
    warning_zones = sum(1 for v in values if 0.2 <= v < 0.35)
    
    # Overall field health assessment - only if significant issues
    if avg_ndvi < 0.25 and critical_zones > 2:
        recommendations.append({
            "type": "critical",
            "zone": "Field Management",
            "message": f"Multiple zones showing poor health (avg NDVI: {avg_ndvi:.2f}). Field-wide assessment needed.",
            "priority": 1,
            "actions": [
                "Review irrigation system coverage",
                "Conduct soil analysis",
                "Check for pest or disease issues"
            ]
        })
    
    # Uniformity analysis - only if really uneven
    if ndvi_variance > 0.15 and (max_ndvi - min_ndvi) > 0.4:
        recommendations.append({
            "type": "warning",
            "zone": "Field Uniformity",
            "message": "Uneven vegetation health across field zones detected.",
            "priority": 2,
            "actions": [
                "Check irrigation system uniformity",
                "Evaluate soil conditions across field",
                "Consider variable rate fertilizer application"
            ]
        })
    
    # Add one general seasonal recommendation only
    current_month = datetime.now().month
    if current_month in [6, 7, 8]:  # Summer
        recommendations.append({
            "type": "info",
            "zone": "Seasonal Care",
            "message": "Peak growing season - monitor water stress closely.",
            "priority": 3,
            "actions": [
                "Increase irrigation monitoring",
                "Watch for heat stress signs"
            ]
        })
    elif current_month in [3, 4, 5]:  # Spring
        recommendations.append({
            "type": "info",
            "zone": "Seasonal Care",
            "message": "Spring growth period - optimize nutrition and water.",
            "priority": 3,
            "actions": [
                "Consider fertilizer application",
                "Ensure adequate soil moisture"
            ]
        })
    
    return recommendations

def get_zone_name(row, col):
    """
    Convert zone coordinates to descriptive names
    
    Args:
        row: Row index (0-2)
        col: Column index (0-2)
    
    Returns:
        Descriptive zone name
    """
    row_names = ["Northern", "Central", "Southern"]
    col_names = ["Western", "Central", "Eastern"]
    
    if row == 1 and col == 1:
        return "Center Zone"
    elif row == 1:
        return f"Central {col_names[col]} Zone"
    elif col == 1:
        return f"{row_names[row]} Central Zone"
    else:
        return f"{row_names[row]} {col_names[col]} Zone"

def calculate_variance(values):
    """Calculate variance of NDVI values"""
    if not values:
        return 0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance

def get_seasonal_recommendations(month, avg_ndvi):
    """
    Generate season-specific recommendations
    
    Args:
        month: Current month (1-12)
        avg_ndvi: Average NDVI value
    
    Returns:
        List of seasonal recommendations
    """
    recommendations = []
    
    # Spring (March-May)
    if month in [3, 4, 5]:
        if avg_ndvi < 0.4:
            recommendations.append({
                "type": "info",
                "zone": "Seasonal",
                "message": "Spring growth appears slow. Consider early season fertilization.",
                "priority": 3,
                "actions": [
                    "Apply nitrogen fertilizer",
                    "Ensure adequate soil moisture",
                    "Monitor temperature conditions"
                ]
            })
    
    # Summer (June-August)
    elif month in [6, 7, 8]:
        recommendations.append({
            "type": "info",
            "zone": "Seasonal",
            "message": "Peak growing season. Monitor irrigation needs closely.",
            "priority": 3,
            "actions": [
                "Increase irrigation frequency",
                "Monitor for heat stress",
                "Watch for pest activity"
            ]
        })
    
    # Fall (September-November)
    elif month in [9, 10, 11]:
        recommendations.append({
            "type": "info",
            "zone": "Seasonal",
            "message": "Harvest season approaching. Prepare for crop maturity assessment.",
            "priority": 4,
            "actions": [
                "Monitor crop maturity",
                "Plan harvest timing",
                "Reduce irrigation as appropriate"
            ]
        })
    
    # Winter (December-February)
    else:
        recommendations.append({
            "type": "info",
            "zone": "Seasonal",
            "message": "Winter season. Plan for next growing season.",
            "priority": 5,
            "actions": [
                "Plan crop rotation",
                "Soil preparation",
                "Equipment maintenance"
            ]
        })
    
    return recommendations
