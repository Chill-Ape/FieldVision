let map;
let drawnItems;
let drawControl;
let currentPolygon = null;

function initializeMap() {
    // Initialize map centered on a default location
    map = L.map('map').setView([40.7128, -74.0060], 10);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    // Initialize drawn items layer
    drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    
    // Initialize draw control
    drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
            polygon: {
                allowIntersection: false,
                drawError: {
                    color: '#e1e100',
                    message: '<strong>Error:</strong> Shape edges cannot cross!'
                },
                shapeOptions: {
                    color: '#28a745',
                    fillColor: '#28a745',
                    fillOpacity: 0.2,
                    weight: 2
                }
            },
            rectangle: false,
            circle: false,
            circlemarker: false,
            marker: false,
            polyline: false
        },
        edit: {
            featureGroup: drawnItems,
            remove: true
        }
    });
    
    map.addControl(drawControl);
    
    // Handle drawing events
    map.on(L.Draw.Event.CREATED, function(e) {
        handleDrawCreated(e);
    });
    
    map.on(L.Draw.Event.EDITED, function(e) {
        handleDrawEdited(e);
    });
    
    map.on(L.Draw.Event.DELETED, function(e) {
        handleDrawDeleted(e);
    });
    
    // Try to get user's location
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            map.setView([lat, lng], 13);
            
            // Add a marker for user's location
            L.marker([lat, lng])
                .addTo(map)
                .bindPopup('Your Location')
                .openPopup();
        }, function(error) {
            console.log('Geolocation error:', error);
        });
    }
    
    // Setup UI event handlers
    setupUIHandlers();
}

function handleDrawCreated(e) {
    const layer = e.layer;
    
    // Remove existing polygon if any
    if (currentPolygon) {
        drawnItems.removeLayer(currentPolygon);
    }
    
    // Add new polygon
    drawnItems.addLayer(layer);
    currentPolygon = layer;
    
    // Update UI
    updateFieldStats(layer);
    enableSaveButton();
    
    console.log('Polygon created:', layer.getLatLngs());
}

function handleDrawEdited(e) {
    const layers = e.layers;
    layers.eachLayer(function(layer) {
        updateFieldStats(layer);
        console.log('Polygon edited:', layer.getLatLngs());
    });
}

function handleDrawDeleted(e) {
    currentPolygon = null;
    hideFieldStats();
    disableSaveButton();
    console.log('Polygon deleted');
}

function updateFieldStats(layer) {
    const latLngs = layer.getLatLngs()[0]; // Get first ring for polygon
    
    // Calculate approximate area (this is a rough calculation)
    const area = calculatePolygonArea(latLngs);
    const perimeter = calculatePolygonPerimeter(latLngs);
    
    // Update UI
    document.getElementById('fieldArea').textContent = area.toFixed(2);
    document.getElementById('fieldPerimeter').textContent = perimeter.toFixed(2);
    document.getElementById('fieldStats').style.display = 'block';
}

function hideFieldStats() {
    document.getElementById('fieldStats').style.display = 'none';
}

function enableSaveButton() {
    const saveButton = document.getElementById('saveField');
    saveButton.disabled = false;
}

function disableSaveButton() {
    const saveButton = document.getElementById('saveField');
    saveButton.disabled = true;
}

function setupUIHandlers() {
    // Save field button
    document.getElementById('saveField').addEventListener('click', function() {
        saveField();
    });
    
    // Clear drawing button
    document.getElementById('clearDrawing').addEventListener('click', function() {
        clearAllDrawings();
    });
    
    // Field name input validation
    document.getElementById('fieldName').addEventListener('input', function() {
        validateForm();
    });
    
    // Address search functionality
    document.getElementById('searchButton').addEventListener('click', function() {
        searchAddress();
    });
    
    // Enter key support for address search
    document.getElementById('addressSearch').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchAddress();
        }
    });
}

function validateForm() {
    const fieldName = document.getElementById('fieldName').value.trim();
    const hasPolygon = currentPolygon !== null;
    const saveButton = document.getElementById('saveField');
    
    saveButton.disabled = !fieldName || !hasPolygon;
}

function saveField() {
    const fieldName = document.getElementById('fieldName').value.trim();
    
    if (!fieldName) {
        alert('Please enter a field name');
        return;
    }
    
    if (!currentPolygon) {
        alert('Please draw a field boundary first');
        return;
    }
    
    // Get polygon coordinates
    const latLngs = currentPolygon.getLatLngs()[0];
    const coordinates = latLngs.map(latlng => [latlng.lat, latlng.lng]);
    
    // Prepare data for API
    const fieldData = {
        name: fieldName,
        polygon: coordinates
    };
    
    // Show loading state
    const saveButton = document.getElementById('saveField');
    const originalText = saveButton.innerHTML;
    saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving...';
    saveButton.disabled = true;
    
    // Send to API
    fetch('/api/save_field', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(fieldData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success modal
            const modal = new bootstrap.Modal(document.getElementById('successModal'));
            modal.show();
            
            // Reset form
            resetForm();
        } else {
            alert('Failed to save field: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Save error:', error);
        alert('Network error occurred while saving field');
    })
    .finally(() => {
        // Reset button
        saveButton.innerHTML = originalText;
        saveButton.disabled = false;
        validateForm();
    });
}

function clearAllDrawings() {
    drawnItems.clearLayers();
    currentPolygon = null;
    hideFieldStats();
    disableSaveButton();
}

function resetForm() {
    document.getElementById('fieldName').value = '';
    clearAllDrawings();
}

function calculatePolygonArea(latLngs) {
    // Simple area calculation using the shoelace formula
    // This is an approximation and doesn't account for Earth's curvature
    let area = 0;
    const n = latLngs.length;
    
    for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        area += latLngs[i].lat * latLngs[j].lng;
        area -= latLngs[j].lat * latLngs[i].lng;
    }
    
    area = Math.abs(area) / 2;
    
    // Convert to approximate hectares (very rough conversion)
    // 1 degree ≈ 111 km, so 1 degree² ≈ 12321 km² ≈ 1,232,100 hectares
    const hectares = area * 1232100;
    
    return hectares;
}

function calculatePolygonPerimeter(latLngs) {
    let perimeter = 0;
    
    for (let i = 0; i < latLngs.length; i++) {
        const current = latLngs[i];
        const next = latLngs[(i + 1) % latLngs.length];
        
        // Calculate distance between two points using Haversine formula
        const distance = calculateDistance(current.lat, current.lng, next.lat, next.lng);
        perimeter += distance;
    }
    
    return perimeter;
}

function calculateDistance(lat1, lng1, lat2, lng2) {
    // Haversine formula for calculating distance between two points on Earth
    const R = 6371; // Earth's radius in kilometers
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) * Math.sin(dLng / 2);
    
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c;
    
    return distance;
}

// Utility function to convert coordinates for different APIs
function convertCoordinatesForAPI(latLngs) {
    return latLngs.map(latlng => ({
        lat: latlng.lat,
        lng: latlng.lng
    }));
}

// Function to load a field polygon (for field detail page)
function loadFieldPolygon(coordinates, fieldName) {
    if (!map) {
        console.error('Map not initialized');
        return;
    }
    
    // Convert coordinates to LatLng objects
    const latLngs = coordinates.map(coord => L.latLng(coord[0], coord[1]));
    
    // Create polygon
    const polygon = L.polygon(latLngs, {
        color: '#28a745',
        fillColor: '#28a745',
        fillOpacity: 0.2,
        weight: 2
    });
    
    // Add to map
    polygon.addTo(map);
    
    // Fit map to polygon bounds
    map.fitBounds(polygon.getBounds(), { padding: [20, 20] });
    
    // Add popup
    polygon.bindPopup(`<strong>${fieldName}</strong><br>Field Boundary`);
    
    return polygon;
}

function searchAddress() {
    const address = document.getElementById('addressSearch').value.trim();
    
    if (!address) {
        alert('Please enter an address to search');
        return;
    }
    
    const searchButton = document.getElementById('searchButton');
    const originalHTML = searchButton.innerHTML;
    searchButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    searchButton.disabled = true;
    
    // Use Nominatim (OpenStreetMap) geocoding service
    const geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`;
    
    fetch(geocodeUrl)
        .then(response => response.json())
        .then(data => {
            if (data && data.length > 0) {
                const result = data[0];
                const lat = parseFloat(result.lat);
                const lng = parseFloat(result.lon);
                
                // Move map to the location
                map.setView([lat, lng], 15);
                
                // Add a temporary marker
                if (window.searchMarker) {
                    map.removeLayer(window.searchMarker);
                }
                
                window.searchMarker = L.marker([lat, lng])
                    .addTo(map)
                    .bindPopup(`<strong>${result.display_name}</strong><br><small>Click to remove marker</small>`)
                    .openPopup();
                
                // Remove marker when clicked
                window.searchMarker.on('click', function() {
                    map.removeLayer(window.searchMarker);
                    window.searchMarker = null;
                });
                
                // Clear search input
                document.getElementById('addressSearch').value = '';
                
            } else {
                alert('Location not found. Please try a different address or be more specific.');
            }
        })
        .catch(error => {
            console.error('Geocoding error:', error);
            alert('Error searching for location. Please check your internet connection and try again.');
        })
        .finally(() => {
            searchButton.innerHTML = originalHTML;
            searchButton.disabled = false;
        });
}

// Export functions for use in other scripts
window.mapUtils = {
    initializeMap,
    loadFieldPolygon,
    calculateDistance,
    convertCoordinatesForAPI,
    searchAddress
};
