from app import db
from datetime import datetime
import json

class Field(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    polygon_data = db.Column(db.Text, nullable=False)  # JSON string of coordinates
    center_lat = db.Column(db.Float, nullable=False)
    center_lng = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_analyzed = db.Column(db.DateTime)
    cached_ndvi_image = db.Column(db.LargeBinary)  # Store NDVI image bytes
    ndvi_cache_date = db.Column(db.DateTime)  # When NDVI was cached
    cached_rgb_image = db.Column(db.LargeBinary)  # Store RGB satellite image bytes
    rgb_cache_date = db.Column(db.DateTime)  # When RGB image was cached
    
    # Additional vegetation index caches
    cached_ndre_image = db.Column(db.LargeBinary)  # Store NDRE image bytes
    ndre_cache_date = db.Column(db.DateTime)  # When NDRE was cached
    cached_moisture_image = db.Column(db.LargeBinary)  # Store Moisture index image bytes
    moisture_cache_date = db.Column(db.DateTime)  # When Moisture was cached
    cached_evi_image = db.Column(db.LargeBinary)  # Store EVI image bytes
    evi_cache_date = db.Column(db.DateTime)  # When EVI was cached
    cached_ndwi_image = db.Column(db.LargeBinary)  # Store NDWI image bytes
    ndwi_cache_date = db.Column(db.DateTime)  # When NDWI was cached
    cached_chlorophyll_image = db.Column(db.LargeBinary)  # Store Chlorophyll image bytes
    chlorophyll_cache_date = db.Column(db.DateTime)  # When Chlorophyll was cached
    
    # Relationship to analyses
    analyses = db.relationship('FieldAnalysis', backref='field', lazy=True, cascade='all, delete-orphan')
    
    def get_polygon_coordinates(self):
        """Return polygon coordinates as a list of [lat, lng] pairs"""
        return json.loads(self.polygon_data)
    
    def set_polygon_coordinates(self, coordinates):
        """Set polygon coordinates from a list of [lat, lng] pairs"""
        self.polygon_data = json.dumps(coordinates)
    
    def calculate_area_acres(self):
        """Calculate field area in acres using Shoelace formula"""
        coords = self.get_polygon_coordinates()
        if len(coords) < 3:
            return 0.0
        
        # Convert to radians and calculate area using spherical excess
        import math
        total_area = 0.0
        n = len(coords)
        
        for i in range(n):
            j = (i + 1) % n
            lat1, lng1 = math.radians(coords[i][0]), math.radians(coords[i][1])
            lat2, lng2 = math.radians(coords[j][0]), math.radians(coords[j][1])
            
            # Simple approximation for small areas
            total_area += (lng2 - lng1) * (2 + math.sin(lat1) + math.sin(lat2))
        
        # Convert to acres (rough approximation)
        area_sq_meters = abs(total_area) * 6378137 * 6378137 / 2
        area_acres = area_sq_meters * 0.000247105  # Convert sq meters to acres
        return area_acres
    
    def cache_ndvi_image(self, image_bytes):
        """Cache NDVI image bytes for this field"""
        self.cached_ndvi_image = image_bytes
        self.ndvi_cache_date = datetime.utcnow()
        self.last_analyzed = datetime.utcnow()
        db.session.commit()
    
    def get_cached_ndvi_image(self):
        """Get cached NDVI image if available"""
        return self.cached_ndvi_image
    
    def has_cached_ndvi(self):
        """Check if field has a cached NDVI image"""
        return self.cached_ndvi_image is not None
    
    def is_ndvi_cache_fresh(self, max_age_days=30):
        """Check if cached NDVI is still fresh (within max_age_days)"""
        if not self.ndvi_cache_date:
            return False
        age = datetime.utcnow() - self.ndvi_cache_date
        return age.days <= max_age_days
    
    def cache_rgb_image(self, image_bytes):
        """Cache RGB satellite image bytes for this field"""
        self.cached_rgb_image = image_bytes
        self.rgb_cache_date = datetime.utcnow()
    
    def get_cached_rgb_image(self):
        """Get cached RGB satellite image if available"""
        return self.cached_rgb_image
    
    def has_cached_rgb(self):
        """Check if field has a cached RGB satellite image"""
        return self.cached_rgb_image is not None
    
    def is_rgb_cache_fresh(self, max_age_days=30):
        """Check if cached RGB image is still fresh (within max_age_days)"""
        if not self.rgb_cache_date:
            return False
        age = datetime.utcnow() - self.rgb_cache_date
        return age.days <= max_age_days
    
    # Generic methods for all vegetation index types
    def cache_vegetation_index_image(self, index_type, image_bytes):
        """Cache vegetation index image bytes for this field"""
        setattr(self, f'cached_{index_type}_image', image_bytes)
        setattr(self, f'{index_type}_cache_date', datetime.utcnow())
    
    def get_cached_vegetation_index_image(self, index_type):
        """Get cached vegetation index image if available"""
        return getattr(self, f'cached_{index_type}_image', None)
    
    def has_cached_vegetation_index(self, index_type):
        """Check if field has a cached vegetation index image"""
        cached_image = getattr(self, f'cached_{index_type}_image', None)
        return cached_image is not None
    
    def is_vegetation_index_cache_fresh(self, index_type, max_age_days=30):
        """Check if cached vegetation index is still fresh (within max_age_days)"""
        cache_date = getattr(self, f'{index_type}_cache_date', None)
        if not cache_date:
            return False
        age = datetime.utcnow() - cache_date
        return age.days <= max_age_days

class FieldAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey('field.id'), nullable=False)
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    ndvi_data = db.Column(db.Text)  # JSON string of NDVI values per zone
    health_scores = db.Column(db.Text)  # JSON string of health scores per zone
    recommendations = db.Column(db.Text)  # JSON string of AI recommendations
    weather_data = db.Column(db.Text)  # JSON string of weather information
    ai_analysis_data = db.Column(db.Text)  # JSON string of comprehensive AI analysis
    
    def get_ndvi_data(self):
        """Return NDVI data as a dictionary"""
        return json.loads(self.ndvi_data) if self.ndvi_data else {}
    
    def set_ndvi_data(self, data):
        """Set NDVI data from a dictionary"""
        self.ndvi_data = json.dumps(data)
    
    def get_health_scores(self):
        """Return health scores as a dictionary"""
        return json.loads(self.health_scores) if self.health_scores else {}
    
    def set_health_scores(self, data):
        """Set health scores from a dictionary"""
        self.health_scores = json.dumps(data)
    
    def get_recommendations(self):
        """Return recommendations as a list"""
        return json.loads(self.recommendations) if self.recommendations else []
    
    def set_recommendations(self, data):
        """Set recommendations from a list"""
        self.recommendations = json.dumps(data)
    
    def get_weather_data(self):
        """Return weather data as a dictionary"""
        return json.loads(self.weather_data) if self.weather_data else {}
    
    def set_weather_data(self, data):
        """Set weather data from a dictionary"""
        self.weather_data = json.dumps(data)
    
    def get_ai_analysis_data(self):
        """Return comprehensive AI analysis data as a dictionary"""
        return json.loads(self.ai_analysis_data) if self.ai_analysis_data else {}
    
    def set_ai_analysis_data(self, data):
        """Set comprehensive AI analysis data from a dictionary"""
        self.ai_analysis_data = json.dumps(data)
