import logging
from datetime import datetime

def generate_recommendations(ndvi_data, zones):
    """
    Generate AI-powered recommendations based on NDVI data and zone analysis
    
    Args:
        ndvi_data: Dictionary with zone IDs and NDVI values
        zones: Dictionary with zone information
    
    Returns:
        List of recommendation dictionaries
    """
    try:
        recommendations = []
        
        if not ndvi_data:
            return [{"type": "error", "message": "No NDVI data available for analysis"}]
        
        # Analyze each zone
        for zone_id, ndvi_value in ndvi_data.items():
            zone_recommendations = analyze_zone_health(zone_id, ndvi_value)
            recommendations.extend(zone_recommendations)
        
        # Add overall field recommendations
        overall_recommendations = analyze_overall_field_health(ndvi_data)
        recommendations.extend(overall_recommendations)
        
        # Sort recommendations by priority
        recommendations.sort(key=lambda x: x.get('priority', 5))
        
        logging.info(f"Generated {len(recommendations)} recommendations")
        return recommendations
        
    except Exception as e:
        logging.error(f"Error generating recommendations: {str(e)}")
        return [{"type": "error", "message": "Failed to generate recommendations"}]

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
    
    # NDVI-based recommendations
    if ndvi_value < 0.1:
        recommendations.append({
            "type": "critical",
            "zone": zone_name,
            "message": f"Critical vegetation stress detected in {zone_name}. Immediate irrigation and soil testing recommended.",
            "priority": 1,
            "actions": [
                "Increase irrigation frequency",
                "Test soil pH and nutrients",
                "Check for pest or disease issues",
                "Consider replanting if necessary"
            ]
        })
    elif ndvi_value < 0.3:
        recommendations.append({
            "type": "warning",
            "zone": zone_name,
            "message": f"Moderate vegetation stress in {zone_name}. Monitor closely and consider intervention.",
            "priority": 2,
            "actions": [
                "Increase irrigation in this area",
                "Monitor for signs of disease or pests",
                "Consider fertilizer application",
                "Check drainage conditions"
            ]
        })
    elif ndvi_value < 0.5:
        recommendations.append({
            "type": "info",
            "zone": zone_name,
            "message": f"Fair vegetation health in {zone_name}. Some improvement possible.",
            "priority": 3,
            "actions": [
                "Monitor irrigation needs",
                "Consider nutrient supplementation",
                "Regular health monitoring"
            ]
        })
    elif ndvi_value > 0.7:
        recommendations.append({
            "type": "success",
            "zone": zone_name,
            "message": f"Excellent vegetation health in {zone_name}. Continue current management practices.",
            "priority": 4,
            "actions": [
                "Maintain current irrigation schedule",
                "Continue monitoring",
                "Use as reference for other zones"
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
    
    # Overall field health assessment
    if avg_ndvi < 0.3:
        recommendations.append({
            "type": "critical",
            "zone": "Overall Field",
            "message": "Overall field health is poor. Comprehensive intervention needed.",
            "priority": 1,
            "actions": [
                "Review irrigation system coverage",
                "Conduct comprehensive soil analysis",
                "Evaluate crop variety suitability",
                "Consider consulting agricultural specialist"
            ]
        })
    elif avg_ndvi > 0.6:
        recommendations.append({
            "type": "success",
            "zone": "Overall Field",
            "message": "Overall field health is excellent. Maintain current practices.",
            "priority": 5,
            "actions": [
                "Continue current management",
                "Document successful practices",
                "Monitor for seasonal changes"
            ]
        })
    
    # Uniformity analysis
    if ndvi_variance > 0.1:
        recommendations.append({
            "type": "warning",
            "zone": "Field Uniformity",
            "message": "Significant variation in vegetation health across field zones.",
            "priority": 2,
            "actions": [
                "Check irrigation system uniformity",
                "Evaluate soil conditions across field",
                "Consider variable rate application of inputs",
                "Address drainage issues if present"
            ]
        })
    
    # Seasonal recommendations
    current_month = datetime.now().month
    seasonal_recs = get_seasonal_recommendations(current_month, avg_ndvi)
    recommendations.extend(seasonal_recs)
    
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
