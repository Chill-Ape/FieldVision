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

class FieldAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey('field.id'), nullable=False)
    analysis_date = db.Column(db.DateTime, default=datetime.utcnow)
    ndvi_data = db.Column(db.Text)  # JSON string of NDVI values per zone
    health_scores = db.Column(db.Text)  # JSON string of health scores per zone
    recommendations = db.Column(db.Text)  # JSON string of AI recommendations
    weather_data = db.Column(db.Text)  # JSON string of weather information
    
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
