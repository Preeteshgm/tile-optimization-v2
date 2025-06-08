// Matching Processor JavaScript file
// Handles cut piece matching and optimization

class MatchingProcessor {
    constructor() {
        this.matchingResults = null;
        this.cleanTables = null;
        this.apartmentSummaries = null;
    }

    /**
     * Run cut piece matching (Step 8)
     * @param {Object} params - Matching parameters
     * @param {Function} onComplete - Callback when complete
     */
    runMatching(params, onComplete) {
        // Show loading overlay
        if (window.showLoading) {
            window.showLoading('Running cut piece matching...');
        }

        // Default tolerance ranges
        const toleranceRanges = params.tolerance_ranges || [10, 20, 40, 60, 80, 100];

        // Send request to server
        fetch('/step8', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tolerance_ranges: toleranceRanges,
                ...params
            })
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            if (data.error) {
                console.error('Error in matching process:', data.error);
                if (onComplete) {
                    onComplete(false, data.error);
                }
            } else {
                // Store results
                this.matchingResults = data;
                this.apartmentSummaries = data.apartment_summaries;
                
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

            console.error('Error in matching process:', error);
            if (onComplete) {
                onComplete(false, 'Network error: ' + error.message);
            }
        });
    }

    /**
     * Visualize apartment matches
     * @param {String} apartmentName - Apartment to visualize
     * @param {Function} onComplete - Callback when complete
     */
    visualizeApartment(apartmentName, onComplete) {
        // Show loading overlay
        if (window.showLoading) {
            window.showLoading('Creating visualization...');
        }

        // Send request to server
        fetch('/step8/visualize_apartment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                apartment_name: apartmentName
            })
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading overlay
            if (window.hideLoading) {
                window.hideLoading();
            }

            if (data.error) {
                console.error('Error creating visualization:', data.error);
                if (onComplete) {
                    onComplete(false, data.error);
                }
            } else {
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

            console.error('Error creating visualization:', error);
            if (onComplete) {
                onComplete(false, 'Network error: ' + error.message);
            }
        });
    }

    /**
     * Get apartment summaries
     * @returns {Object} Apartment summaries
     */
    getApartmentSummaries() {
        return this.apartmentSummaries || {};
    }

    /**
     * Update match table display
     * @param {String} tableId - Table element ID
     * @param {String} apartment - Apartment name
     */
    updateMatchTable(tableId, apartment) {
        const table = document.getElementById(tableId);
        if (!table || !this.matchingResults) return;

        const summaries = this.apartmentSummaries || {};
        const summary = summaries[apartment] || {};

        // Clear existing content
        table.innerHTML = '';

        // Create summary rows
        const rows = [
            { label: 'Total Pieces', value: summary.total_pieces || 0 },
            { label: 'Matched Pieces', value: summary.matched_pieces || 0 },
            { label: 'Unmatched Pieces', value: summary.unmatched_pieces || 0 },
            { label: 'Match Percentage', value: `${summary.match_percentage || 0}%` },
            { label: 'Apartment Matches', value: summary.apartment_matches || 0 },
            { label: 'Inventory Matches', value: summary.inventory_matches || 0 }
        ];

        rows.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.label}</td>
                <td><strong>${row.value}</strong></td>
            `;
            table.appendChild(tr);
        });
    }
}

// Export the MatchingProcessor class
window.MatchingProcessor = MatchingProcessor;