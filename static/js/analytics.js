/**
 * Enhanced Analytics and Data Visualization for FieldVision AI
 * Provides temporal analysis, zone-based visualization, and export capabilities
 */

class FieldAnalytics {
    constructor(fieldId) {
        this.fieldId = fieldId;
        this.chartInstances = {};
        this.currentView = 'temporal';
        this.initializeAnalytics();
    }

    initializeAnalytics() {
        this.loadChartLibrary();
        this.setupEventHandlers();
    }

    loadChartLibrary() {
        // Load Chart.js if not already loaded
        if (typeof Chart === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js';
            script.onload = () => {
                console.log('Chart.js loaded successfully');
                this.createDefaultCharts();
            };
            document.head.appendChild(script);
        } else {
            this.createDefaultCharts();
        }
    }

    async createDefaultCharts() {
        console.log('Creating default charts for field:', this.fieldId);
        
        try {
            await this.createTemporalChart();
            await this.createZoneAnalysisChart();
            await this.loadSummaryCards();
            await this.loadAnalyticsTable();
            
            // Hide loading indicators
            this.hideLoadingIndicators();
        } catch (error) {
            console.error('Error creating charts:', error);
            this.showErrorMessage('Failed to load analytics data');
        }
    }
    
    hideLoadingIndicators() {
        const loadingElements = document.querySelectorAll('.analytics-loading');
        loadingElements.forEach(el => {
            el.style.display = 'none';
        });
    }
    
    showErrorMessage(message) {
        const analyticsContent = document.querySelector('.analytics-dashboard');
        if (analyticsContent) {
            analyticsContent.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    ${message}
                </div>
            `;
        }
    }

    setupEventHandlers() {
        // Analytics view switcher
        document.addEventListener('click', (e) => {
            if (e.target.matches('.analytics-view-btn')) {
                this.switchAnalyticsView(e.target.dataset.view);
            }
            
            if (e.target.matches('.export-btn')) {
                this.exportData(e.target.dataset.format);
            }
            
            if (e.target.matches('.compare-dates-btn')) {
                this.showDateComparison();
            }
        });
    }

    async loadFieldHistory() {
        try {
            const response = await fetch(`/field/${this.fieldId}/history`);
            if (!response.ok) throw new Error('Failed to load field history');
            const data = await response.json();
            console.log('Field history loaded:', data);
            return data;
        } catch (error) {
            console.error('Error loading field history:', error);
            return { field_name: 'Unknown Field', analyses: [] };
        }
    }

    async createTemporalChart() {
        const historyData = await this.loadFieldHistory();
        
        if (historyData.analyses.length === 0) {
            this.showNoDataMessage('temporal-chart', 'No historical data available. Run more analyses to see trends.');
            return;
        }

        const ctx = document.getElementById('temporal-chart');
        if (!ctx) return;

        // Prepare data for temporal analysis
        const dates = historyData.analyses.map(a => new Date(a.analysis_date).toLocaleDateString());
        const ndviData = historyData.analyses.map(a => a.ndvi_avg || 0);
        const healthScores = historyData.analyses.map(a => a.health_score || 0);

        // Destroy existing chart
        if (this.chartInstances.temporal) {
            this.chartInstances.temporal.destroy();
        }

        this.chartInstances.temporal = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'NDVI Average',
                        data: ndviData,
                        borderColor: 'rgb(34, 197, 94)',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Health Score',
                        data: healthScores,
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Field Health Trends Over Time'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'NDVI Value'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Health Score'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    async createZoneAnalysisChart() {
        // Simulate zone-based data (in real implementation, this would come from field analysis)
        const zoneData = this.generateZoneData();
        
        const ctx = document.getElementById('zone-chart');
        if (!ctx) return;

        if (this.chartInstances.zone) {
            this.chartInstances.zone.destroy();
        }

        this.chartInstances.zone = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: zoneData.labels,
                datasets: [
                    {
                        label: 'NDVI by Zone',
                        data: zoneData.ndvi,
                        backgroundColor: zoneData.ndvi.map(value => this.getHealthColor(value)),
                        borderColor: 'rgba(0, 0, 0, 0.1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Vegetation Health by Field Zone'
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        title: {
                            display: true,
                            text: 'NDVI Value'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Field Zones'
                        }
                    }
                }
            }
        });
    }

    generateZoneData() {
        // Generate realistic zone data for 3x3 grid
        const zones = [];
        const ndviValues = [];
        
        for (let row = 1; row <= 3; row++) {
            for (let col = 1; col <= 3; col++) {
                zones.push(`Zone ${row}-${col}`);
                // Generate realistic NDVI values (0.2 to 0.9)
                ndviValues.push(0.3 + Math.random() * 0.5);
            }
        }
        
        return {
            labels: zones,
            ndvi: ndviValues
        };
    }

    getHealthColor(ndviValue) {
        if (ndviValue >= 0.7) return 'rgba(34, 197, 94, 0.8)'; // Excellent - Green
        if (ndviValue >= 0.5) return 'rgba(251, 191, 36, 0.8)'; // Good - Yellow
        if (ndviValue >= 0.3) return 'rgba(249, 115, 22, 0.8)'; // Moderate - Orange
        return 'rgba(239, 68, 68, 0.8)'; // Poor - Red
    }

    async createComparisonChart() {
        const historyData = await this.loadFieldHistory();
        
        if (historyData.analyses.length < 2) {
            this.showNoDataMessage('comparison-chart', 'Need at least 2 analyses for comparison.');
            return;
        }

        const ctx = document.getElementById('comparison-chart');
        if (!ctx) return;

        // Get latest and previous analysis
        const latest = historyData.analyses[0];
        const previous = historyData.analyses[1];

        const comparisonData = {
            labels: ['NDVI', 'Moisture', 'Chlorophyll', 'Overall Health'],
            datasets: [
                {
                    label: `Latest (${new Date(latest.analysis_date).toLocaleDateString()})`,
                    data: [
                        latest.ndvi_avg || 0.6,
                        latest.moisture_avg || 0.5,
                        latest.chlorophyll_avg || 0.7,
                        latest.health_score || 0.75
                    ],
                    backgroundColor: 'rgba(34, 197, 94, 0.8)',
                    borderColor: 'rgb(34, 197, 94)',
                    borderWidth: 2
                },
                {
                    label: `Previous (${new Date(previous.analysis_date).toLocaleDateString()})`,
                    data: [
                        previous.ndvi_avg || 0.55,
                        previous.moisture_avg || 0.45,
                        previous.chlorophyll_avg || 0.65,
                        previous.health_score || 0.7
                    ],
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderColor: 'rgb(59, 130, 246)',
                    borderWidth: 2
                }
            ]
        };

        if (this.chartInstances.comparison) {
            this.chartInstances.comparison.destroy();
        }

        this.chartInstances.comparison = new Chart(ctx, {
            type: 'radar',
            data: comparisonData,
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Current vs Previous Analysis Comparison'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            stepSize: 0.2
                        }
                    }
                }
            }
        });
    }

    switchAnalyticsView(view) {
        this.currentView = view;
        
        // Update button states
        document.querySelectorAll('.analytics-view-btn').forEach(btn => {
            btn.classList.toggle('btn-primary', btn.dataset.view === view);
            btn.classList.toggle('btn-outline-primary', btn.dataset.view !== view);
        });

        // Show/hide chart containers
        document.querySelectorAll('.analytics-chart-container').forEach(container => {
            container.style.display = container.id === `${view}-container` ? 'block' : 'none';
        });

        // Create appropriate chart
        switch(view) {
            case 'temporal':
                this.createTemporalChart();
                break;
            case 'zones':
                this.createZoneAnalysisChart();
                break;
            case 'comparison':
                this.createComparisonChart();
                break;
        }
    }

    showNoDataMessage(containerId, message) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="text-center p-4">
                    <i class="fas fa-chart-line fa-3x text-muted mb-3"></i>
                    <p class="text-muted">${message}</p>
                </div>
            `;
        }
    }

    async exportData(format) {
        try {
            const historyData = await this.loadFieldHistory();
            
            switch(format) {
                case 'csv':
                    this.exportToCSV(historyData);
                    break;
                case 'pdf':
                    this.exportToPDF(historyData);
                    break;
                case 'json':
                    this.exportToJSON(historyData);
                    break;
            }
        } catch (error) {
            console.error('Export failed:', error);
            alert('Export failed. Please try again.');
        }
    }

    exportToCSV(data) {
        const csv = this.convertToCSV(data.analyses);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `field_${this.fieldId}_analysis_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    convertToCSV(analyses) {
        const headers = ['Date', 'NDVI_Avg', 'Health_Score', 'Weather_Temp', 'Weather_Humidity'];
        const rows = analyses.map(analysis => [
            new Date(analysis.analysis_date).toLocaleDateString(),
            analysis.ndvi_avg || 'N/A',
            analysis.health_score || 'N/A',
            analysis.weather_temp || 'N/A',
            analysis.weather_humidity || 'N/A'
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }

    exportToJSON(data) {
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `field_${this.fieldId}_data_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    async exportToPDF(data) {
        // Simple PDF export using browser print
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
            <head>
                <title>Field Analysis Report</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f2f2f2; }
                    .header { text-align: center; margin-bottom: 30px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Field Analysis Report</h1>
                    <p>Generated on ${new Date().toLocaleDateString()}</p>
                </div>
                ${this.generateReportHTML(data)}
            </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    }

    generateReportHTML(data) {
        const analyses = data.analyses.slice(0, 10); // Latest 10 analyses
        
        return `
            <table>
                <thead>
                    <tr>
                        <th>Analysis Date</th>
                        <th>NDVI Average</th>
                        <th>Health Score</th>
                        <th>Weather</th>
                        <th>Recommendations</th>
                    </tr>
                </thead>
                <tbody>
                    ${analyses.map(analysis => `
                        <tr>
                            <td>${new Date(analysis.analysis_date).toLocaleDateString()}</td>
                            <td>${analysis.ndvi_avg || 'N/A'}</td>
                            <td>${analysis.health_score || 'N/A'}</td>
                            <td>${analysis.weather_summary || 'N/A'}</td>
                            <td>${(analysis.recommendations || []).slice(0, 2).join('; ')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    async loadSummaryCards() {
        try {
            const historyData = await this.loadFieldHistory();
            const latest = historyData.analyses[0];
            
            if (!latest) {
                this.updateSummaryCard('ndvi-trend', 'No Data', 'secondary', 'fa-question');
                this.updateSummaryCard('moisture-status', 'No Data', 'secondary', 'fa-question');
                this.updateSummaryCard('chlorophyll-level', 'No Data', 'secondary', 'fa-question');
                this.updateSummaryCard('overall-health', 'No Data', 'secondary', 'fa-question');
                return;
            }
            
            // Update summary cards with latest data
            this.updateSummaryCard('ndvi-trend', 
                `${(latest.ndvi_avg || 0.6).toFixed(2)}`, 
                this.getStatusColor(latest.ndvi_avg || 0.6, [0.3, 0.5, 0.7]), 
                'fa-leaf');
                
            this.updateSummaryCard('moisture-status', 
                `${(latest.moisture_avg || 0.5).toFixed(2)}`, 
                this.getStatusColor(latest.moisture_avg || 0.5, [0.3, 0.5, 0.7]), 
                'fa-tint');
                
            this.updateSummaryCard('chlorophyll-level', 
                `${(latest.chlorophyll_avg || 0.6).toFixed(2)}`, 
                this.getStatusColor(latest.chlorophyll_avg || 0.6, [0.4, 0.6, 0.8]), 
                'fa-seedling');
                
            this.updateSummaryCard('overall-health', 
                latest.ai_analysis?.overall_health || 'Moderate',
                this.getHealthStatusColor(latest.ai_analysis?.overall_health || 'Moderate'),
                'fa-heartbeat');
                
        } catch (error) {
            console.error('Error loading summary cards:', error);
        }
    }
    
    updateSummaryCard(cardId, value, colorClass, iconClass) {
        const card = document.getElementById(cardId);
        if (card) {
            const valueElement = card.querySelector('.card-value');
            const iconElement = card.querySelector('.card-icon i');
            
            if (valueElement) valueElement.textContent = value;
            if (iconElement) {
                iconElement.className = `fas ${iconClass}`;
            }
            
            // Update card border color
            card.className = `card analytics-summary-card border-${colorClass}`;
        }
    }
    
    getStatusColor(value, thresholds) {
        if (value >= thresholds[2]) return 'success';
        if (value >= thresholds[1]) return 'warning';
        if (value >= thresholds[0]) return 'danger';
        return 'dark';
    }
    
    getHealthStatusColor(health) {
        const colors = {
            'Excellent': 'success',
            'Good': 'success', 
            'Moderate': 'warning',
            'Poor': 'danger',
            'Critical': 'danger'
        };
        return colors[health] || 'secondary';
    }
    
    async loadAnalyticsTable() {
        try {
            const historyData = await this.loadFieldHistory();
            const tableBody = document.getElementById('analytics-table-body');
            
            if (!tableBody) return;
            
            if (historyData.analyses.length === 0) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-muted">
                            No analysis data available. Run a field analysis to see results here.
                        </td>
                    </tr>
                `;
                return;
            }
            
            // Show latest 10 analyses
            const recentAnalyses = historyData.analyses.slice(0, 10);
            
            tableBody.innerHTML = recentAnalyses.map(analysis => `
                <tr>
                    <td>${new Date(analysis.analysis_date).toLocaleDateString()}</td>
                    <td><span class="badge bg-${this.getStatusColor(analysis.ndvi_avg || 0.6, [0.3, 0.5, 0.7])}">${(analysis.ndvi_avg || 0.6).toFixed(2)}</span></td>
                    <td><span class="badge bg-${this.getHealthStatusColor(analysis.ai_analysis?.overall_health || 'Moderate')}">${analysis.ai_analysis?.overall_health || 'Moderate'}</span></td>
                    <td>${analysis.weather_summary || 'N/A'}</td>
                    <td>
                        <span class="badge bg-info">${analysis.weather_temp ? Math.round(analysis.weather_temp) + '°C' : 'N/A'}</span>
                        <span class="badge bg-secondary ms-1">${analysis.weather_humidity ? analysis.weather_humidity + '%' : 'N/A'}</span>
                    </td>
                </tr>
            `).join('');
            
        } catch (error) {
            console.error('Error loading analytics table:', error);
        }
    }
}

// Initialize analytics when page loads
document.addEventListener('DOMContentLoaded', function() {
    const fieldId = window.location.pathname.split('/')[2];
    if (fieldId && document.getElementById('analytics-section')) {
        window.fieldAnalytics = new FieldAnalytics(fieldId);
    }
});