# FieldVision AI - Satellite-Powered Agricultural Intelligence Platform

## Overview

FieldVision AI is a comprehensive agricultural intelligence platform that leverages satellite imagery, weather data, and AI analysis to provide farmers with actionable insights for crop management. The application enables users to define field boundaries, analyze vegetation health through NDVI (Normalized Difference Vegetation Index), and receive AI-powered recommendations for optimal field management.

## System Architecture

### Frontend Architecture
- **Web Interface**: Flask-based web application with responsive Bootstrap UI
- **Interactive Mapping**: Leaflet.js with drawing capabilities for field boundary definition
- **Single Page Application (SPA)**: AJAX-driven navigation for seamless user experience
- **Visualization Components**: Custom vegetation index visualizations and zone-based analysis displays

### Backend Architecture
- **Web Framework**: Python Flask with SQLAlchemy ORM
- **Database**: PostgreSQL with SQLAlchemy models for field and analysis data storage
- **API Integration**: Sentinel Hub API for satellite imagery and OpenWeatherMap for weather data
- **AI Processing**: OpenAI GPT integration for intelligent agricultural recommendations
- **Image Processing**: PIL (Pillow) and NumPy for NDVI image analysis and processing

### Data Storage Solutions
- **Primary Database**: PostgreSQL for structured data (fields, analyses, user data)
- **Binary Storage**: Database BLOB storage for cached NDVI images
- **Coordinate Storage**: JSON-serialized polygon coordinates for field boundaries

## Key Components

### 1. Field Management System
- **Field Model**: Stores field metadata, polygon coordinates, center points, and analysis history
- **Polygon Drawing**: Interactive map interface for defining field boundaries
- **Area Calculation**: Automatic calculation of field area in acres using geospatial algorithms

### 2. Satellite Data Integration
- **NDVI Fetcher**: Interfaces with Sentinel Hub API for vegetation index retrieval
- **Authentication Handler**: OAuth2 token management for Sentinel Hub access
- **Multiple Indices**: Support for NDVI, NDRE, moisture, EVI, NDWI, and chlorophyll indices
- **Image Caching**: Database storage of processed satellite imagery for performance

### 3. AI Analysis Engine
- **Comprehensive Analyzer**: Combines NDVI, weather, and agricultural data for insights
- **Zone-based Processing**: 3x3 grid analysis for targeted field management
- **Recommendation Engine**: Rule-based system generating actionable agricultural advice
- **Report Generation**: Automated creation of farmer-friendly analysis reports

### 4. Weather Integration
- **Weather Service**: Real-time weather data retrieval and analysis
- **Agricultural Correlation**: Weather impact assessment on vegetation health
- **Historical Data**: Integration of weather patterns with vegetation analysis

### 5. Automated Monitoring
- **Scheduled Analysis**: Automated field monitoring with 24-hour intervals
- **Change Detection**: Significant vegetation change identification and alerting
- **Email Notifications**: SendGrid integration for automated farmer alerts

## Data Flow

1. **Field Definition**: User draws field boundaries on interactive map
2. **Coordinate Storage**: Polygon coordinates saved as JSON in PostgreSQL
3. **Satellite Request**: System queries Sentinel Hub API for NDVI imagery
4. **Image Processing**: Raw satellite data processed into vegetation indices
5. **Zone Analysis**: Field divided into 3x3 grid for detailed analysis
6. **Weather Integration**: Current and historical weather data retrieved
7. **AI Processing**: Combined data fed into AI analysis engine
8. **Report Generation**: Comprehensive farmer-friendly reports created
9. **Monitoring Loop**: Automated periodic re-analysis and alerting

## External Dependencies

### Required APIs
- **Sentinel Hub**: Satellite imagery and vegetation indices (requires credentials)
- **OpenWeatherMap**: Weather data integration (API key required)
- **OpenAI**: AI-powered agricultural recommendations (API key required)
- **SendGrid**: Email notifications for monitoring alerts (API key required)

### Python Dependencies
- **Flask**: Web framework and routing
- **SQLAlchemy**: Database ORM and management
- **Requests**: HTTP client for API integrations
- **Pillow**: Image processing and manipulation
- **NumPy**: Numerical computing for NDVI analysis
- **Shapely**: Geospatial geometry operations
- **Gunicorn**: Production WSGI server

## Deployment Strategy

### Development Environment
- **Replit Integration**: Configured for Replit development environment
- **SQLite Fallback**: Local development database when PostgreSQL unavailable
- **Environment Variables**: Configuration through environment variables
- **Hot Reload**: Development server with automatic reload capability

### Production Deployment
- **Autoscale Target**: Configured for automatic scaling based on demand
- **Gunicorn WSGI**: Production-ready Python application server
- **PostgreSQL**: Production database with connection pooling
- **Port Configuration**: Exposed on port 5000 with external port mapping

### Configuration Management
- **Environment-based**: Database URLs and API keys from environment
- **Fallback Values**: Graceful degradation when external services unavailable
- **Demo Mode**: Sample data generation when API credentials missing

## Changelog
- June 12, 2025. Initial setup
- June 14, 2025. Enhanced Data Visualization & Analytics dashboard with mobile responsiveness
  - Fixed JavaScript syntax errors and loading issues in analytics dashboard
  - Implemented mobile-responsive layout for summary cards and data tables
  - Created separate mobile/desktop layouts for project headers
  - Added Chart.js placeholders to replace problematic interactive charts
  - Improved table responsiveness with mobile-specific card layouts
  - Fixed horizontal scrolling issues on mobile devices

## User Preferences

Preferred communication style: Simple, everyday language.