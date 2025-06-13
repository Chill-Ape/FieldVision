"""
Visual field analysis using OpenAI's vision capabilities
Analyzes actual satellite imagery to understand field layout, crop patterns, and infrastructure
"""

import base64
import json
import logging
from typing import Dict, Optional


class VisualFieldAnalyzer:
    """Analyzes satellite imagery using OpenAI vision to understand field layout and characteristics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_field_imagery(self, ndvi_image_bytes: bytes, field_info: Dict, rgb_image_bytes: Optional[bytes] = None) -> Dict:
        """
        Analyze satellite imagery to understand field layout, crop patterns, and infrastructure
        
        Args:
            ndvi_image_bytes: NDVI satellite image as bytes
            field_info: Basic field information (name, area, coordinates)
            rgb_image_bytes: Optional RGB true color satellite image as bytes
            
        Returns:
            Dictionary containing visual analysis results
        """
        try:
            from openai import OpenAI
            import os
            
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
            
            # Convert images to base64
            ndvi_image_b64 = base64.b64encode(ndvi_image_bytes).decode('utf-8')
            
            # Create comprehensive visual analysis prompt
            prompt = self._create_visual_analysis_prompt(field_info, has_rgb=rgb_image_bytes is not None)
            
            # Prepare content with both images if available
            content = [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{ndvi_image_b64}",
                        "detail": "high"
                    }
                }
            ]
            
            # Add RGB image if available
            if rgb_image_bytes:
                rgb_image_b64 = base64.b64encode(rgb_image_bytes).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{rgb_image_b64}",
                        "detail": "high"
                    }
                })
            
            response = client.chat.completions.create(
                model="gpt-4o",  # Latest model with vision capabilities
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.2,
                timeout=30  # Add timeout to prevent hanging
            )
            
            visual_analysis = json.loads(response.choices[0].message.content or "{}")
            
            self.logger.info(f"Visual field analysis completed: {len(visual_analysis)} analysis sections")
            return visual_analysis
            
        except Exception as e:
            self.logger.error(f"Visual field analysis failed: {str(e)}")
            return self._get_fallback_visual_analysis(field_info)
    
    def _create_visual_analysis_prompt(self, field_info: Dict, has_rgb: bool = False) -> str:
        """Create detailed prompt for visual satellite image analysis"""
        
        if has_rgb:
            prompt = f"""You are an expert agricultural consultant analyzing satellite imagery. You have been provided with TWO images:

IMAGE 1 - NDVI (Vegetation Health Analysis):
- Dark green/black areas = Healthy, dense vegetation
- Light green/yellow areas = Moderate vegetation health  
- Orange/red areas = Stressed vegetation, bare soil, or non-vegetated areas

IMAGE 2 - RGB True Color Satellite Image:
- Natural color satellite view showing actual field layouts, infrastructure, and land features
- Use this to identify field shapes, buildings, roads, and spatial relationships

Field: {field_info.get('name', 'Unknown')} ({field_info.get('area_acres', 0):.1f} acres)"""
        else:
            prompt = f"""You are an expert agricultural consultant analyzing satellite NDVI imagery. This is a vegetation health analysis image where:
- Dark green/black areas = Healthy, dense vegetation
- Light green/yellow areas = Moderate vegetation health  
- Orange/red areas = Stressed vegetation, bare soil, or non-vegetated areas
- The image shows field: {field_info.get('name', 'Unknown')} ({field_info.get('area_acres', 0):.1f} acres)"""

        prompt += """

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
{
    "field_layout": {
        "total_field_sections": "Number of distinct field areas visible",
        "field_types": "Description of field shapes (circular pivot fields, rectangular plots, etc.)",
        "dominant_pattern": "Primary field layout pattern observed"
    },
    "infrastructure": {
        "buildings": "Description of buildings/structures and their locations",
        "roads": "Description of roads and their relationship to fields",
        "irrigation": "Description of irrigation infrastructure observed"
    },
    "spatial_analysis": {
        "field_positions": "Spatial description of field locations relative to each other",
        "navigation_references": "Landmark-based descriptions for field identification"
    },
    "vegetation_health": {
        "healthy_areas": "Specific description of areas with good vegetation health",
        "stressed_areas": "Specific description of areas showing vegetation stress"
    },
    "agricultural_insights": {
        "farming_type": "Type of agricultural operation observed",
        "irrigation_method": "Irrigation methods identified from field patterns",
        "crop_diversity": "Evidence of different crops or rotation patterns"
    },
    "spatial_recommendations": "Specific recommendations using spatial references from the visual analysis"
}

CRITICAL: Base your analysis ONLY on what you can actually see in the satellite image. Be specific about spatial relationships and use the vegetation index colors to assess health. Use the layout information for spatially-aware recommendations."""

        return prompt
    
    def _get_fallback_visual_analysis(self, field_info: Dict) -> Dict:
        """Provide fallback analysis when visual analysis fails"""
        return {
            "field_layout": {
                "total_field_sections": "Unable to analyze - visual processing unavailable",
                "field_types": "Visual analysis required for field pattern identification",
                "dominant_pattern": "Cannot determine without satellite image analysis"
            },
            "infrastructure": {
                "buildings": "Visual analysis required for infrastructure identification",
                "roads": "Cannot identify road patterns without image processing",
                "irrigation": "Irrigation infrastructure analysis requires visual data"
            },
            "spatial_analysis": {
                "field_positions": "Spatial relationships require visual satellite analysis",
                "navigation_references": "Cannot provide navigation references without visual data"
            },
            "vegetation_health": {
                "healthy_areas": "Vegetation health assessment requires NDVI image analysis",
                "stressed_areas": "Stress identification requires visual satellite data"
            },
            "agricultural_insights": {
                "farming_type": "Agricultural operation type requires visual field analysis",
                "irrigation_method": "Irrigation method identification needs satellite imagery",
                "crop_diversity": "Crop pattern analysis requires visual satellite data"
            },
            "spatial_recommendations": f"Visual analysis required for spatially-specific recommendations for {field_info.get('name', 'this field')}"
        }
    
    def integrate_visual_analysis_into_prompt(self, visual_analysis: Dict) -> str:
        """Generate prompt addition that includes visual analysis findings"""
        
        if not visual_analysis or "field_layout" not in visual_analysis:
            return ""
        
        integration_text = "\n\n=== VISUAL SATELLITE IMAGE ANALYSIS ===\n"
        
        # Field Layout Information
        layout = visual_analysis.get("field_layout", {})
        if layout:
            integration_text += f"FIELD LAYOUT:\n"
            integration_text += f"- Total field sections: {layout.get('total_field_sections', 'Unknown')}\n"
            integration_text += f"- Field types: {layout.get('field_types', 'Not specified')}\n"
            integration_text += f"- Dominant pattern: {layout.get('dominant_pattern', 'Not identified')}\n\n"
        
        # Infrastructure Information
        infrastructure = visual_analysis.get("infrastructure", {})
        if infrastructure:
            integration_text += "INFRASTRUCTURE:\n"
            integration_text += f"- Buildings: {infrastructure.get('buildings', 'None identified')}\n"
            integration_text += f"- Roads: {infrastructure.get('roads', 'None identified')}\n"
            integration_text += f"- Irrigation: {infrastructure.get('irrigation', 'None identified')}\n\n"
        
        # Spatial Analysis
        spatial = visual_analysis.get("spatial_analysis", {})
        if spatial:
            integration_text += "SPATIAL FIELD RELATIONSHIPS:\n"
            integration_text += f"- Field positions: {spatial.get('field_positions', 'Not analyzed')}\n"
            integration_text += f"- Navigation references: {spatial.get('navigation_references', 'Not available')}\n\n"
        
        # Vegetation Health by Location
        vegetation = visual_analysis.get("vegetation_health", {})
        if vegetation:
            integration_text += "VEGETATION HEALTH BY LOCATION:\n"
            integration_text += f"- Healthy areas: {vegetation.get('healthy_areas', 'Not identified')}\n"
            integration_text += f"- Stressed areas: {vegetation.get('stressed_areas', 'Not identified')}\n\n"
        
        # Agricultural Insights
        agricultural = visual_analysis.get("agricultural_insights", {})
        if agricultural:
            integration_text += "AGRICULTURAL SETUP:\n"
            integration_text += f"- Farming type: {agricultural.get('farming_type', 'Not determined')}\n"
            integration_text += f"- Irrigation method: {agricultural.get('irrigation_method', 'Not identified')}\n"
            integration_text += f"- Crop diversity: {agricultural.get('crop_diversity', 'Not assessed')}\n\n"
        
        integration_text += "CRITICAL: Use these SPECIFIC visual observations in your analysis.\n"
        integration_text += "Reference fields by their observed positions and characteristics.\n"
        integration_text += "Use landmark-based navigation for spatial recommendations.\n"
        integration_text += "Base vegetation health assessment on the actual satellite imagery patterns observed.\n"
        integration_text += "Provide spatially-aware recommendations using the field layout information.\n"
        
        return integration_text