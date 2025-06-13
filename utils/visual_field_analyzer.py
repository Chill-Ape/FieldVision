"""
Visual field analysis using OpenAI's vision capabilities
Analyzes actual satellite imagery to understand field layout, crop patterns, and infrastructure
"""

import base64
import logging
from typing import Dict, List, Optional, Tuple
import json

class VisualFieldAnalyzer:
    """Analyzes satellite imagery using OpenAI vision to understand field layout and characteristics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_field_imagery(self, ndvi_image_bytes: bytes, field_info: Dict) -> Dict:
        """
        Analyze satellite imagery to understand field layout, crop patterns, and infrastructure
        
        Args:
            ndvi_image_bytes: NDVI satellite image as bytes
            field_info: Basic field information (name, area, coordinates)
            
        Returns:
            Dictionary containing visual analysis results
        """
        try:
            from openai import OpenAI
            import os
            
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
            
            # Convert image to base64
            image_base64 = base64.b64encode(ndvi_image_bytes).decode('utf-8')
            
            # Create comprehensive visual analysis prompt
            prompt = self._create_visual_analysis_prompt(field_info)
            
            response = client.chat.completions.create(
                model="gpt-4o",  # Latest model with vision capabilities
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.2
            )
            
            visual_analysis = json.loads(response.choices[0].message.content or "{}")
            
            self.logger.info(f"Visual field analysis completed: {len(visual_analysis)} analysis sections")
            return visual_analysis
            
        except Exception as e:
            self.logger.error(f"Visual field analysis failed: {str(e)}")
            return self._get_fallback_visual_analysis(field_info)
    
    def _create_visual_analysis_prompt(self, field_info: Dict) -> str:
        """Create detailed prompt for visual satellite image analysis"""
        
        prompt = f"""You are an expert agricultural consultant analyzing satellite NDVI imagery. This is a vegetation health analysis image where:
- Dark green/black areas = Healthy, dense vegetation
- Light green/yellow areas = Moderate vegetation health  
- Orange/red areas = Stressed vegetation, bare soil, or non-vegetated areas
- The image shows field: {field_info.get('name', 'Unknown')} ({field_info.get('area_acres', 0):.1f} acres)

VISUAL ANALYSIS INSTRUCTIONS:
Carefully examine this satellite image and provide detailed spatial analysis. Look for:

1. FIELD LAYOUT PATTERNS:
   - Circle/pivot irrigation fields vs. rectangular fields
   - Field boundaries and shapes
   - Size variations between different field sections
   - Orientation and positioning relative to each other

2. INFRASTRUCTURE IDENTIFICATION:
   - Buildings, farmhouses, barns (usually appear as small geometric shapes)
   - Roads (linear features crossing the area)
   - Irrigation infrastructure (center pivots, channels)
   - Other structures or facilities

3. SPATIAL RELATIONSHIPS:
   - Describe fields by their relative positions (northernmost, southernmost, center, etc.)
   - Use ordinal descriptions (first field from north, second largest circle, etc.)
   - Reference infrastructure as landmarks for navigation

4. VEGETATION HEALTH PATTERNS:
   - Which specific fields/areas show healthy vegetation (dark green)
   - Which areas show stress or problems (yellow/orange/red)
   - Patterns within individual fields (uniform vs. patchy)

5. AGRICULTURAL SETUP ANALYSIS:
   - Type of farming operation (row crops, orchards, mixed agriculture)
   - Irrigation method evidence (pivot circles, flood irrigation rectangles)
   - Crop rotation or different crop types visible

Provide response in JSON format:
{{
    "field_layout": {{
        "total_field_sections": "Number of distinct field areas visible",
        "field_types": "Description of field shapes (circular pivot fields, rectangular plots, etc.)",
        "dominant_pattern": "Primary field layout pattern observed"
    }},
    "infrastructure": {{
        "buildings": "Description of buildings/structures and their locations",
        "roads": "Description of road network and layout",
        "irrigation_systems": "Type and layout of irrigation infrastructure",
        "other_features": "Any other notable infrastructure"
    }},
    "spatial_description": {{
        "field_arrangement": "Detailed description of how fields are arranged spatially",
        "navigation_references": "Landmark-based descriptions for farmer navigation",
        "relative_positions": "Ordinal descriptions of field positions"
    }},
    "vegetation_analysis": {{
        "healthy_areas": "Which specific fields/zones show healthy vegetation",
        "stressed_areas": "Which specific fields/zones show vegetation stress",
        "patterns": "Vegetation health patterns within and between fields",
        "variations": "Notable differences between field sections"
    }},
    "farming_operation": {{
        "operation_type": "Type of agricultural operation observed",
        "crop_evidence": "Evidence of crop types or farming practices",
        "management_style": "Intensive vs. extensive, modern vs. traditional indicators"
    }},
    "detailed_field_inventory": [
        {{
            "field_id": "Field 1",
            "shape": "circular/rectangular/irregular",
            "position": "spatial location description",
            "size_relative": "large/medium/small compared to others",
            "health_status": "vegetation health in this specific field",
            "notable_features": "any unique characteristics"
        }}
    ]
}}

CRITICAL: Base your analysis ONLY on what you can actually see in the satellite image. Be specific about spatial relationships and use the vegetation index colors to assess health. Describe the layout as if giving directions to a farmer walking the property."""

        return prompt
    
    def _get_fallback_visual_analysis(self, field_info: Dict) -> Dict:
        """Provide fallback analysis when visual analysis fails"""
        return {
            "field_layout": {
                "total_field_sections": "Analysis unavailable",
                "field_types": "Visual analysis failed - unable to determine field layout",
                "dominant_pattern": "Unknown"
            },
            "infrastructure": {
                "buildings": "Visual analysis unavailable",
                "roads": "Visual analysis unavailable", 
                "irrigation_systems": "Visual analysis unavailable",
                "other_features": "Visual analysis unavailable"
            },
            "spatial_description": {
                "field_arrangement": "Detailed visual analysis not available",
                "navigation_references": "Unable to provide landmark references",
                "relative_positions": "Spatial analysis unavailable"
            },
            "vegetation_analysis": {
                "healthy_areas": "Visual vegetation analysis unavailable",
                "stressed_areas": "Visual vegetation analysis unavailable", 
                "patterns": "Pattern analysis unavailable",
                "variations": "Variation analysis unavailable"
            },
            "farming_operation": {
                "operation_type": "Unable to determine from visual analysis",
                "crop_evidence": "Visual crop analysis unavailable",
                "management_style": "Management assessment unavailable"
            },
            "detailed_field_inventory": [
                {
                    "field_id": "Analysis Failed",
                    "shape": "unknown",
                    "position": "visual analysis unavailable", 
                    "size_relative": "unknown",
                    "health_status": "visual assessment unavailable",
                    "notable_features": "visual analysis failed"
                }
            ]
        }
    
    def integrate_visual_analysis_into_prompt(self, visual_analysis: Dict) -> str:
        """Generate prompt addition that includes visual analysis findings"""
        
        if not visual_analysis or visual_analysis.get('field_layout', {}).get('total_field_sections') == "Analysis unavailable":
            return "\nVISUAL ANALYSIS: Satellite imagery visual analysis not available."
        
        prompt_addition = f"""

VISUAL SATELLITE IMAGE ANALYSIS:
═══════════════════════════════

FIELD LAYOUT OBSERVED:
{visual_analysis.get('field_layout', {}).get('field_arrangement', 'Not available')}

Field Types: {visual_analysis.get('field_layout', {}).get('field_types', 'Not specified')}
Total Sections: {visual_analysis.get('field_layout', {}).get('total_field_sections', 'Unknown')}

INFRASTRUCTURE VISIBLE:
Buildings: {visual_analysis.get('infrastructure', {}).get('buildings', 'None identified')}
Roads: {visual_analysis.get('infrastructure', {}).get('roads', 'None identified')}
Irrigation: {visual_analysis.get('infrastructure', {}).get('irrigation_systems', 'Not identified')}

SPATIAL FIELD ARRANGEMENT:
{visual_analysis.get('spatial_description', {}).get('field_arrangement', 'Not available')}

Navigation References: {visual_analysis.get('spatial_description', {}).get('navigation_references', 'Not available')}

VEGETATION HEALTH BY LOCATION:
Healthy Areas: {visual_analysis.get('vegetation_analysis', {}).get('healthy_areas', 'Not specified')}
Stressed Areas: {visual_analysis.get('vegetation_analysis', {}).get('stressed_areas', 'Not specified')}

DETAILED FIELD INVENTORY:"""

        # Add individual field details
        for field in visual_analysis.get('detailed_field_inventory', []):
            prompt_addition += f"""
- {field.get('field_id', 'Unknown')}: {field.get('shape', 'unknown')} field, {field.get('position', 'location unknown')}, {field.get('health_status', 'health unknown')}"""

        prompt_addition += f"""

CRITICAL ANALYSIS INSTRUCTIONS:
- Use these SPECIFIC visual observations in your analysis
- Reference fields by their observed positions and characteristics
- Use landmark-based navigation (e.g., "circular field north of the buildings")
- Base vegetation health assessment on the actual satellite imagery patterns observed
- Provide spatially-aware recommendations using the field layout information
"""

        return prompt_addition