"""
Geospatial context analysis for field monitoring
Identifies roads, buildings, water bodies, and actual cropland areas
"""

import logging
import requests
from typing import Dict, List, Tuple, Optional
import json

class GeospatialContextAnalyzer:
    """Analyzes geospatial context to identify non-crop areas like roads, buildings, water"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_field_context(self, field_polygon: List[Tuple[float, float]], bbox: List[float]) -> Dict:
        """
        Analyze the geospatial context of a field to identify roads, buildings, water bodies
        
        Args:
            field_polygon: List of (lat, lng) coordinates defining the field boundary
            bbox: Bounding box [min_lng, min_lat, max_lng, max_lat]
            
        Returns:
            Dictionary containing land use classification and exclusion zones
        """
        try:
            context = {
                'roads': [],
                'buildings': [],
                'water_bodies': [],
                'land_cover': {},
                'exclusion_zones': [],
                'actual_cropland_percentage': 100.0,
                'contextual_description': ''
            }
            
            # Get road network
            roads = self._get_road_network(bbox)
            if roads:
                context['roads'] = roads
                context['exclusion_zones'].extend(self._create_road_exclusion_zones(roads))
            
            # Get building footprints
            buildings = self._get_building_footprints(bbox)
            if buildings:
                context['buildings'] = buildings
                context['exclusion_zones'].extend(self._create_building_exclusion_zones(buildings))
            
            # Get water bodies
            water_bodies = self._get_water_bodies(bbox)
            if water_bodies:
                context['water_bodies'] = water_bodies
                context['exclusion_zones'].extend(self._create_water_exclusion_zones(water_bodies))
            
            # Calculate actual cropland percentage
            context['actual_cropland_percentage'] = self._calculate_cropland_percentage(
                field_polygon, context['exclusion_zones']
            )
            
            # Generate contextual description
            context['contextual_description'] = self._generate_context_description(context)
            
            return context
            
        except Exception as e:
            self.logger.error(f"Geospatial context analysis failed: {str(e)}")
            return self._get_fallback_context()
    
    def _get_road_network(self, bbox: List[float]) -> List[Dict]:
        """Get road network from OpenStreetMap Overpass API"""
        try:
            # Overpass API query for roads
            overpass_query = f"""
            [out:json][timeout:25];
            (
              way["highway"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            );
            out geom;
            """
            
            overpass_url = "http://overpass-api.de/api/interpreter"
            response = requests.post(overpass_url, data=overpass_query, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                roads = []
                
                for element in data.get('elements', []):
                    if element.get('type') == 'way' and 'geometry' in element:
                        road_type = element.get('tags', {}).get('highway', 'unknown')
                        roads.append({
                            'type': 'road',
                            'subtype': road_type,
                            'geometry': element['geometry'],
                            'width_estimate': self._estimate_road_width(road_type)
                        })
                
                return roads
                
        except Exception as e:
            self.logger.warning(f"Road network query failed: {str(e)}")
            return []
    
    def _get_building_footprints(self, bbox: List[float]) -> List[Dict]:
        """Get building footprints from OpenStreetMap"""
        try:
            overpass_query = f"""
            [out:json][timeout:25];
            (
              way["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
              relation["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            );
            out geom;
            """
            
            overpass_url = "http://overpass-api.de/api/interpreter"
            response = requests.post(overpass_url, data=overpass_query, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                buildings = []
                
                for element in data.get('elements', []):
                    if 'geometry' in element or 'members' in element:
                        building_type = element.get('tags', {}).get('building', 'yes')
                        buildings.append({
                            'type': 'building',
                            'subtype': building_type,
                            'geometry': element.get('geometry', []),
                            'area_estimate': self._estimate_building_area(element)
                        })
                
                return buildings
                
        except Exception as e:
            self.logger.warning(f"Building footprint query failed: {str(e)}")
            return []
    
    def _get_water_bodies(self, bbox: List[float]) -> List[Dict]:
        """Get water bodies from OpenStreetMap"""
        try:
            overpass_query = f"""
            [out:json][timeout:25];
            (
              way["natural"="water"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
              way["waterway"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
              relation["natural"="water"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            );
            out geom;
            """
            
            overpass_url = "http://overpass-api.de/api/interpreter"
            response = requests.post(overpass_url, data=overpass_query, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                water_bodies = []
                
                for element in data.get('elements', []):
                    if 'geometry' in element:
                        water_type = element.get('tags', {}).get('natural') or element.get('tags', {}).get('waterway', 'water')
                        water_bodies.append({
                            'type': 'water',
                            'subtype': water_type,
                            'geometry': element['geometry']
                        })
                
                return water_bodies
                
        except Exception as e:
            self.logger.warning(f"Water body query failed: {str(e)}")
            return []
    
    def _estimate_road_width(self, road_type: str) -> float:
        """Estimate road width in meters based on highway type"""
        road_widths = {
            'motorway': 12.0,
            'trunk': 10.0,
            'primary': 8.0,
            'secondary': 7.0,
            'tertiary': 6.0,
            'residential': 5.0,
            'service': 3.0,
            'track': 2.0,
            'path': 1.0,
            'footway': 1.0
        }
        return road_widths.get(road_type, 4.0)
    
    def _estimate_building_area(self, element: Dict) -> float:
        """Estimate building area in square meters"""
        # Simplified area calculation - in production could use more sophisticated geometry
        if 'geometry' in element and len(element['geometry']) > 2:
            return len(element['geometry']) * 50.0  # Rough estimate
        return 100.0  # Default building size
    
    def _create_road_exclusion_zones(self, roads: List[Dict]) -> List[Dict]:
        """Create exclusion zones around roads"""
        exclusion_zones = []
        for road in roads:
            exclusion_zones.append({
                'type': 'road_exclusion',
                'description': f"{road['subtype']} road",
                'geometry': road['geometry'],
                'buffer_meters': road['width_estimate'] + 2.0,  # Road width + buffer
                'reason': 'Transportation infrastructure - not cropland'
            })
        return exclusion_zones
    
    def _create_building_exclusion_zones(self, buildings: List[Dict]) -> List[Dict]:
        """Create exclusion zones around buildings"""
        exclusion_zones = []
        for building in buildings:
            exclusion_zones.append({
                'type': 'building_exclusion',
                'description': f"{building['subtype']} building",
                'geometry': building['geometry'],
                'buffer_meters': 10.0,  # 10m buffer around buildings
                'reason': 'Building structure - not cropland'
            })
        return exclusion_zones
    
    def _create_water_exclusion_zones(self, water_bodies: List[Dict]) -> List[Dict]:
        """Create exclusion zones for water bodies"""
        exclusion_zones = []
        for water in water_bodies:
            exclusion_zones.append({
                'type': 'water_exclusion',
                'description': f"{water['subtype']} water body",
                'geometry': water['geometry'],
                'buffer_meters': 5.0,  # 5m buffer around water
                'reason': 'Water body - not cropland'
            })
        return exclusion_zones
    
    def _calculate_cropland_percentage(self, field_polygon: List[Tuple[float, float]], 
                                     exclusion_zones: List[Dict]) -> float:
        """Calculate the percentage of field that is actual cropland"""
        # Simplified calculation - in production would use proper geometric intersection
        base_percentage = 100.0
        
        # Reduce percentage based on number and type of exclusions
        road_penalty = len([z for z in exclusion_zones if z['type'] == 'road_exclusion']) * 5.0
        building_penalty = len([z for z in exclusion_zones if z['type'] == 'building_exclusion']) * 8.0
        water_penalty = len([z for z in exclusion_zones if z['type'] == 'water_exclusion']) * 3.0
        
        total_penalty = min(road_penalty + building_penalty + water_penalty, 80.0)  # Max 80% penalty
        
        return max(base_percentage - total_penalty, 20.0)  # Minimum 20% assumed cropland
    
    def _generate_context_description(self, context: Dict) -> str:
        """Generate human-readable description of field context"""
        descriptions = []
        
        road_count = len(context['roads'])
        building_count = len(context['buildings'])
        water_count = len(context['water_bodies'])
        
        if road_count > 0:
            road_types = list(set([r['subtype'] for r in context['roads']]))
            descriptions.append(f"{road_count} road(s) including {', '.join(road_types[:2])}")
        
        if building_count > 0:
            descriptions.append(f"{building_count} building structure(s)")
        
        if water_count > 0:
            descriptions.append(f"{water_count} water feature(s)")
        
        cropland_pct = context['actual_cropland_percentage']
        
        if descriptions:
            base_desc = f"Field contains {', '.join(descriptions)}. "
        else:
            base_desc = "Field appears to be primarily agricultural land. "
        
        base_desc += f"Estimated {cropland_pct:.0f}% actual cropland area."
        
        return base_desc
    
    def _get_fallback_context(self) -> Dict:
        """Provide fallback context when analysis fails"""
        return {
            'roads': [],
            'buildings': [],
            'water_bodies': [],
            'land_cover': {},
            'exclusion_zones': [],
            'actual_cropland_percentage': 85.0,  # Conservative estimate
            'contextual_description': 'Unable to retrieve detailed geospatial context. Analysis assumes primarily agricultural land use.'
        }
    
    def get_contextual_analysis_prompt(self, context: Dict) -> str:
        """Generate prompt addition for AI analysis that includes geospatial context"""
        
        if not context or context['actual_cropland_percentage'] >= 95:
            return ""
        
        prompt_addition = f"""

IMPORTANT GEOSPATIAL CONTEXT:
{context['contextual_description']}

EXCLUSION ZONES TO CONSIDER:
"""
        
        for zone in context['exclusion_zones'][:5]:  # Limit to top 5 for prompt length
            prompt_addition += f"- {zone['description']}: {zone['reason']}\n"
        
        prompt_addition += f"""
When analyzing vegetation indices, remember that only approximately {context['actual_cropland_percentage']:.0f}% of the area is actual cropland. 

ANALYSIS GUIDELINES:
1. Do not flag roads, buildings, or water areas as crop stress
2. Focus vegetation health analysis only on actual agricultural areas
3. Use landmarks (roads, buildings) as reference points in recommendations
4. Adjust irrigation and treatment recommendations based on actual cropland area
5. Mention exclusion zones in your analysis to provide spatial context
"""

        return prompt_addition