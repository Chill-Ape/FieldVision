// Field analysis utilities and visualization functions

class FieldAnalyzer {
    constructor() {
        this.analysisInProgress = false;
    }
    
    async analyzeField(fieldId) {
        if (this.analysisInProgress) {
            console.log('Analysis already in progress');
            return;
        }
        
        this.analysisInProgress = true;
        
        try {
            const response = await fetch(`/api/analyze_field/${fieldId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Analysis failed');
            }
        } catch (error) {
            console.error('Analysis error:', error);
            throw error;
        } finally {
            this.analysisInProgress = false;
        }
    }
    
    visualizeNDVIData(ndviData, containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Container not found:', containerId);
            return;
        }
        
        // Create 3x3 grid visualization
        let html = '<div class="ndvi-grid">';
        
        for (let row = 0; row < 3; row++) {
            html += '<div class="ndvi-row">';
            for (let col = 0; col < 3; col++) {
                const zoneId = `zone_${row}_${col}`;
                const ndviValue = ndviData[zoneId] || 0;
                const color = this.getNDVIColor(ndviValue);
                
                html += `<div class="ndvi-cell" style="background-color: ${color};">`;
                html += `<div class="ndvi-value">${ndviValue.toFixed(3)}</div>`;
                html += `<div class="zone-label">${this.getZoneName(row, col)}</div>`;
                html += `</div>`;
            }
            html += '</div>';
        }
        
        html += '</div>';
        container.innerHTML = html;
    }
    
    getNDVIColor(ndviValue) {
        // Color mapping based on NDVI value
        if (ndviValue > 0.6) return '#28a745'; // Green - Healthy
        if (ndviValue > 0.4) return '#6f42c1'; // Purple - Good
        if (ndviValue > 0.3) return '#ffc107'; // Yellow - Moderate
        if (ndviValue > 0.1) return '#fd7e14'; // Orange - Poor
        return '#dc3545'; // Red - Very poor
    }
    
    getZoneName(row, col) {
        const rowNames = ['N', 'C', 'S']; // North, Center, South
        const colNames = ['W', 'C', 'E']; // West, Center, East
        return `${rowNames[row]}${colNames[col]}`;
    }
    
    createHealthChart(healthScores, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error('Canvas not found:', canvasId);
            return;
        }
        
        const ctx = canvas.getContext('2d');
        
        // Count health categories
        const healthCounts = { healthy: 0, moderate: 0, stressed: 0 };
        Object.values(healthScores).forEach(health => {
            if (healthCounts.hasOwnProperty(health)) {
                healthCounts[health]++;
            }
        });
        
        // Create pie chart
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Healthy', 'Moderate', 'Stressed'],
                datasets: [{
                    data: [healthCounts.healthy, healthCounts.moderate, healthCounts.stressed],
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    title: {
                        display: true,
                        text: 'Field Health Distribution'
                    }
                }
            }
        });
    }
    
    displayRecommendations(recommendations, containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Container not found:', containerId);
            return;
        }
        
        let html = '';
        
        recommendations.forEach((rec, index) => {
            let alertClass = 'info';
            let icon = 'fas fa-info-circle';
            
            switch (rec.type) {
                case 'critical':
                    alertClass = 'danger';
                    icon = 'fas fa-exclamation-triangle';
                    break;
                case 'warning':
                    alertClass = 'warning';
                    icon = 'fas fa-exclamation-circle';
                    break;
                case 'success':
                    alertClass = 'success';
                    icon = 'fas fa-check-circle';
                    break;
            }
            
            html += `<div class="alert alert-${alertClass} mb-3">`;
            html += `<div class="d-flex align-items-start">`;
            html += `<i class="${icon} me-3 mt-1"></i>`;
            html += `<div class="flex-grow-1">`;
            html += `<h6 class="mb-1">${rec.zone || 'General Recommendation'}</h6>`;
            html += `<p class="mb-2">${rec.message}</p>`;
            
            if (rec.actions && rec.actions.length > 0) {
                html += `<div class="small">`;
                html += `<strong>Suggested Actions:</strong>`;
                html += `<ul class="mb-0 mt-1">`;
                rec.actions.forEach(action => {
                    html += `<li>${action}</li>`;
                });
                html += `</ul>`;
                html += `</div>`;
            }
            
            html += `</div>`;
            html += `</div>`;
            html += `</div>`;
        });
        
        if (html === '') {
            html = '<div class="text-muted text-center py-3">No recommendations available</div>';
        }
        
        container.innerHTML = html;
    }
    
    displayWeatherInfo(weatherData, containerId) {
        const container = document.getElementById(containerId);
        if (!container || !weatherData.current) {
            return;
        }
        
        const current = weatherData.current;
        
        let html = `
            <div class="weather-current mb-3">
                <div class="row text-center">
                    <div class="col-4">
                        <div class="weather-metric">
                            <div class="weather-value">${current.temperature}°C</div>
                            <div class="weather-label">Temperature</div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="weather-metric">
                            <div class="weather-value">${current.humidity}%</div>
                            <div class="weather-label">Humidity</div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="weather-metric">
                            <div class="weather-value">${current.rainfall}mm</div>
                            <div class="weather-label">Rain</div>
                        </div>
                    </div>
                </div>
                <div class="text-center mt-2">
                    <small class="text-muted text-capitalize">${current.description}</small>
                </div>
            </div>
        `;
        
        if (weatherData.forecast && weatherData.forecast.length > 0) {
            html += `<div class="weather-forecast">`;
            html += `<h6>3-Day Forecast</h6>`;
            html += `<div class="row">`;
            
            weatherData.forecast.slice(0, 3).forEach(day => {
                const date = new Date(day.date);
                const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
                
                html += `<div class="col-4 text-center">`;
                html += `<div class="forecast-day">`;
                html += `<div class="fw-bold">${dayName}</div>`;
                html += `<div class="small text-muted">${day.temp_max}°/${day.temp_min}°</div>`;
                html += `<div class="small">${day.rainfall}mm</div>`;
                html += `</div>`;
                html += `</div>`;
            });
            
            html += `</div>`;
            html += `</div>`;
        }
        
        container.innerHTML = html;
    }
    
    exportAnalysisData(analysisData, fieldName) {
        // Create downloadable JSON file with analysis data
        const data = {
            fieldName: fieldName,
            analysisDate: new Date().toISOString(),
            ndviData: analysisData.ndvi_data,
            healthScores: analysisData.health_scores,
            recommendations: analysisData.recommendations,
            weatherData: analysisData.weather_data
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${fieldName.replace(/\s+/g, '_')}_analysis_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }
}

// Analysis utilities
const AnalysisUtils = {
    calculateFieldHealth: function(ndviData) {
        const values = Object.values(ndviData);
        const average = values.reduce((sum, val) => sum + val, 0) / values.length;
        
        if (average > 0.6) return { status: 'excellent', color: '#28a745' };
        if (average > 0.4) return { status: 'good', color: '#6f42c1' };
        if (average > 0.3) return { status: 'fair', color: '#ffc107' };
        if (average > 0.1) return { status: 'poor', color: '#fd7e14' };
        return { status: 'critical', color: '#dc3545' };
    },
    
    getIrrigationPriority: function(ndviData, weatherData) {
        const avgNdvi = Object.values(ndviData).reduce((sum, val) => sum + val, 0) / Object.values(ndviData).length;
        const rainfall = weatherData.current?.rainfall || 0;
        const humidity = weatherData.current?.humidity || 50;
        
        let priority = 0;
        
        if (avgNdvi < 0.3) priority += 3;
        else if (avgNdvi < 0.5) priority += 2;
        else priority += 1;
        
        if (rainfall < 2) priority += 2;
        if (humidity < 40) priority += 1;
        
        if (priority >= 5) return 'high';
        if (priority >= 3) return 'medium';
        return 'low';
    },
    
    identifyProblemZones: function(ndviData, threshold = 0.3) {
        const problemZones = [];
        
        for (const [zoneId, ndviValue] of Object.entries(ndviData)) {
            if (ndviValue < threshold) {
                problemZones.push({
                    zone: zoneId,
                    ndvi: ndviValue,
                    severity: ndviValue < 0.1 ? 'critical' : 'moderate'
                });
            }
        }
        
        return problemZones.sort((a, b) => a.ndvi - b.ndvi);
    }
};

// Initialize field analyzer
const fieldAnalyzer = new FieldAnalyzer();

// Export for global use
window.FieldAnalyzer = FieldAnalyzer;
window.fieldAnalyzer = fieldAnalyzer;
window.AnalysisUtils = AnalysisUtils;
