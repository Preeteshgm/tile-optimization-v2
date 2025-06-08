// Data Preparation Processor JavaScript file
// Handles cut piece data preparation and inventory management

class DataPreparationProcessor {
    constructor() {
        this.cutPiecesSummary = null;
        this.inventoryData = null;
        this.hasPattern = false;
        this.halfThreshold = 300;
    }

    /**
     * Prepare apartment data (Step 7A)
     * @param {Function} onComplete - Callback when preparation is complete
     */
    prepareApartmentData(onComplete) {
        // Show loading overlay
        if (window.showLoading) {
            window.showLoading('Preparing apartment data...');
        }

        // Send request to server
        fetch('/step7a', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            if (data.error) {
                console.error('Error preparing apartment data:', data.error);
                if (onComplete) {
                    onComplete(false, data.error);
                }
            } else {
                // Store summary data
                this.cutPiecesSummary = data.summary;
                this.hasPattern = data.summary.has_pattern;
                this.halfThreshold = data.summary.half_threshold;
                
                if (onComplete) {
                    onComplete(true, data);
                }
            }
        })
        .catch(error => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            console.error('Error preparing apartment data:', error);
            if (onComplete) {
                onComplete(false, 'Network error: ' + error.message);
            }
        });
    }

    /**
     * Handle inventory options (Step 7B)
     * @param {Object} params - Inventory parameters
     * @param {Function} onComplete - Callback when complete
     */
    handleInventoryOptions(params, onComplete) {
        // Show loading overlay
        if (window.showLoading) {
            window.showLoading('Processing inventory options...');
        }

        // Send request to server
        fetch('/step7b', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        })
        .then(response => {
            // Check if response is a file download
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/vnd.openxmlformats')) {
                // This is an Excel file download
                return response.blob().then(blob => {
                    // Create download link
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'inventory_template.xlsx';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    
                    // Hide loading overlay
                    if (window.hideLoading) {
                        window.hideLoading();
                    }
                    
                    if (onComplete) {
                        onComplete(true, { templateDownloaded: true });
                    }
                });
            } else {
                // Regular JSON response
                return response.json().then(data => {
                    // Hide loading overlay
                    if (window.hideLoading) {
                        window.hideLoading();
                    }

                    if (data.error) {
                        console.error('Error handling inventory options:', data.error);
                        if (onComplete) {
                            onComplete(false, data.error);
                        }
                    } else {
                        if (onComplete) {
                            onComplete(true, data);
                        }
                    }
                });
            }
        })
        .catch(error => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            console.error('Error handling inventory options:', error);
            if (onComplete) {
                onComplete(false, 'Network error: ' + error.message);
            }
        });
    }

    /**
     * Upload inventory file (Step 7C)
     * @param {File} file - Inventory file to upload
     * @param {Object} params - Additional parameters
     * @param {Function} onComplete - Callback when complete
     */
    uploadInventoryFile(file, params, onComplete) {
        if (!file) {
            if (onComplete) {
                onComplete(false, 'No file selected');
            }
            return;
        }

        // Show loading overlay
        if (window.showLoading) {
            window.showLoading('Uploading inventory file...');
        }

        // Create form data
        const formData = new FormData();
        formData.append('inventory_file', file);
        
        // Add other parameters
        if (params.generate_more !== undefined) {
            formData.append('generate_more', params.generate_more);
        }

        // Send file to server
        fetch('/step7c', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            if (data.error) {
                console.error('Error uploading inventory:', data.error);
                if (onComplete) {
                    onComplete(false, data.error);
                }
            } else {
                // Store inventory data
                this.inventoryData = data.stats;
                
                if (onComplete) {
                    onComplete(true, data);
                }
            }
        })
        .catch(error => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            console.error('Error uploading inventory:', error);
            if (onComplete) {
                onComplete(false, 'Network error: ' + error.message);
            }
        });
    }

    /**
     * Get summary statistics
     * @returns {Object} Summary statistics
     */
    getSummaryStats() {
        return this.cutPiecesSummary || {
            apartment_pieces: 0,
            inventory_pieces: 0,
            total_pieces: 0,
            half_threshold: 300
        };
    }
}

// Export the DataPreparationProcessor class
window.DataPreparationProcessor = DataPreparationProcessor;