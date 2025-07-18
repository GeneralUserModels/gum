/**
 * GUM (General User Models) - Frontend Application
 * Modern JavaScript application for video analysis and user behavior insights
 */

class GUMApp {
    constructor() {
        // Use configuration from injected global variable or fallback to default
        this.apiBaseUrl = window.GUM_CONFIG?.apiBaseUrl || 'http://localhost:8002';
        console.log('GUM Frontend initialized with API base URL:', this.apiBaseUrl);
        
        this.connectionStatus = 'connecting';
        this.uploadProgress = 0;
        this.currentStep = 1;
        this.selectedFile = null;
        this.toastTimeout = null;
        
        // Propositions pagination
        this.currentPropositionsPage = 1;
        
        // Tab management
        this.activeTab = 'upload';
          // Theme management - handle migration from old theme key
        let theme = localStorage.getItem('gum-theme');
        if (!theme) {
            // Default to light theme
            theme = 'light';
            localStorage.setItem('gum-theme', theme);
        }
        this.theme = theme;
        
        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        this.applyTheme();
        this.setupEventListeners();
        this.setupTabNavigation();
        this.setupFileUpload();
        this.setupProgressTracking();
        this.setupPropositionsListeners();
        this.setupQueryListeners();
        await this.checkConnection();
        this.updateConnectionStatus();
        this.loadRecentHistory();
    }

    /**
     * Apply theme to the application
     */
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        const themeIcon = document.querySelector('#themeToggle i');
        if (themeIcon) {
            themeIcon.className = this.theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }

    /**
     * Toggle between light and dark themes
     */    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('gum-theme', this.theme);
        this.applyTheme();
        this.showToast(`Switched to ${this.theme} mode`, 'info');
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Video form submission
        const videoForm = document.getElementById('videoForm');
        if (videoForm) {
            videoForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitVideoAnalysis();
            });
        }

        // Action buttons
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportResults());
        }

        const newAnalysisBtn = document.getElementById('newAnalysisBtn');
        if (newAnalysisBtn) {
            newAnalysisBtn.addEventListener('click', () => this.startNewAnalysis());
        }

        const refreshHistory = document.getElementById('refreshHistory');
        if (refreshHistory) {
            refreshHistory.addEventListener('click', () => this.loadRecentHistory());
        }

        // Remove file button
        const removeFile = document.getElementById('removeFile');
        if (removeFile) {
            removeFile.addEventListener('click', () => this.removeSelectedFile());
        }

        // Database cleanup button
        const cleanupDatabase = document.getElementById('cleanupDatabase');
        if (cleanupDatabase) {
            cleanupDatabase.addEventListener('click', () => this.handleDatabaseCleanup());
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'u':
                        e.preventDefault();
                        this.triggerFileUpload();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.startNewAnalysis();
                        break;
                }
            }
        });

        // Progress bar on scroll
        window.addEventListener('scroll', () => this.updateScrollProgress());
    }

    /**
     * Setup file upload functionality
     */
    setupFileUpload() {
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('videoFile');
        const uploadBtn = document.getElementById('uploadBtn');

        if (!uploadZone || !fileInput) return;

        // Click to upload
        uploadZone.addEventListener('click', () => {
            fileInput.click();
        });

        // File selection
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelection(e.target.files[0]);
            }
        });

        // Drag and drop
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', (e) => {
            if (!uploadZone.contains(e.relatedTarget)) {
                uploadZone.classList.remove('dragover');
            }
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                this.handleFileSelection(e.dataTransfer.files[0]);
            }
        });
    }

    /**
     * Handle file selection and validation
     */
    handleFileSelection(file) {
        // Validate file type
        const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/quicktime'];
        if (!allowedTypes.includes(file.type)) {
            this.showToast('Please select a valid video file (MP4, AVI, MOV, WMV)', 'error');
            return;
        }

        // Validate file size (max 500MB)
        const maxSize = 500 * 1024 * 1024; // 500MB
        if (file.size > maxSize) {
            this.showToast('File size too large. Maximum size is 500MB.', 'error');
            return;
        }

        this.selectedFile = file;
        this.displayFilePreview(file);
        this.enableUploadButton();
    }

    /**
     * Display file preview
     */
    displayFilePreview(file) {
        const uploadZoneContent = document.getElementById('uploadZoneContent');
        const filePreview = document.getElementById('filePreview');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const fileDuration = document.getElementById('fileDuration');
        const previewVideo = document.getElementById('previewVideo');

        if (!uploadZoneContent || !filePreview) return;

        // Hide upload zone, show preview
        uploadZoneContent.style.display = 'none';
        filePreview.style.display = 'block';

        // Set file info
        if (fileName) fileName.textContent = file.name;
        if (fileSize) fileSize.textContent = this.formatFileSize(file.size);

        // Create video URL and set duration
        if (previewVideo) {
            const videoUrl = URL.createObjectURL(file);
            previewVideo.src = videoUrl;
            
            previewVideo.addEventListener('loadedmetadata', () => {
                if (fileDuration) {
                    fileDuration.textContent = this.formatDuration(previewVideo.duration);
                }
            });
        }
    }

    /**
     * Remove selected file
     */
    removeSelectedFile() {
        this.selectedFile = null;
        
        const uploadZoneContent = document.getElementById('uploadZoneContent');
        const filePreview = document.getElementById('filePreview');
        const previewVideo = document.getElementById('previewVideo');
        const fileInput = document.getElementById('videoFile');

        if (uploadZoneContent) uploadZoneContent.style.display = 'block';
        if (filePreview) filePreview.style.display = 'none';
        if (previewVideo) {
            URL.revokeObjectURL(previewVideo.src);
            previewVideo.src = '';
        }
        if (fileInput) fileInput.value = '';

        this.disableUploadButton();
    }

    /**
     * Enable upload button
     */
    enableUploadButton() {
        const uploadBtn = document.getElementById('uploadBtn');
        if (uploadBtn) {
            uploadBtn.disabled = false;
        }
    }

    /**
     * Disable upload button
     */
    disableUploadButton() {
        const uploadBtn = document.getElementById('uploadBtn');
        if (uploadBtn) {
            uploadBtn.disabled = true;
        }
    }

    /**
     * Trigger file upload dialog
     */
    triggerFileUpload() {
        const fileInput = document.getElementById('videoFile');
        if (fileInput) {
            fileInput.click();
        }
    }

    /**
     * Setup progress tracking
     */
    setupProgressTracking() {
        this.progressSteps = [
            { id: 'step1', name: 'Uploading' },
            { id: 'step2', name: 'Processing' },
            { id: 'step3', name: 'Analyzing' },
            { id: 'step4', name: 'Complete' }
        ];
    }

    /**
     * Update progress step
     */
    updateProgressStep(stepNumber, progress = 0) {
        this.currentStep = stepNumber;
        
        // Update progress bar
        const progressFill = document.getElementById('uploadProgress');
        if (progressFill) {
            const totalProgress = ((stepNumber - 1) * 25) + (progress * 25 / 100);
            progressFill.style.width = `${totalProgress}%`;
        }

        // Update progress text
        const progressText = document.getElementById('progressText');
        const progressPercent = document.getElementById('progressPercent');
        
        if (progressText && this.progressSteps[stepNumber - 1]) {
            progressText.textContent = this.progressSteps[stepNumber - 1].name;
        }
        
        if (progressPercent) {
            const totalProgress = ((stepNumber - 1) * 25) + (progress * 25 / 100);
            progressPercent.textContent = `${Math.round(totalProgress)}%`;
        }

        // Update step indicators
        this.progressSteps.forEach((step, index) => {
            const stepElement = document.getElementById(step.id);
            if (stepElement) {
                stepElement.classList.remove('active', 'completed');
                
                if (index + 1 < stepNumber) {
                    stepElement.classList.add('completed');
                } else if (index + 1 === stepNumber) {
                    stepElement.classList.add('active');
                }
            }
        });
    }

    /**
     * Submit video for analysis
     */
    async submitVideoAnalysis() {
        if (!this.selectedFile) {
            this.showToast('Please select a video file first', 'error');
            return;
        }

        if (this.connectionStatus !== 'connected') {
            this.showToast('Cannot connect to analysis service. Please check connection.', 'error');
            return;
        }

        // Get form data
        const fps = document.getElementById('videoFps')?.value || 0.4;
        const userName = document.getElementById('videoUserName')?.value.trim();
        // Default analysis - send all analysis types
        const analysisTypes = ['behavior', 'activity', 'workflow', 'productivity'];

        // Show progress section
        const progressSection = document.getElementById('progressSection');
        if (progressSection) {
            progressSection.style.display = 'block';
            progressSection.scrollIntoView({ behavior: 'smooth' });
        }

        // Disable form
        this.disableForm();

        try {
            // Step 1: Upload
            this.updateProgressStep(1, 0);
            
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('fps', fps);
            if (userName) formData.append('user_name', userName);
            formData.append('observer_name', 'web_interface');

            // Create upload request with progress tracking
            const response = await this.uploadWithProgress(formData);
            
            if (response.ok) {
                const result = await response.json();
                this.updateProgressStep(4, 100);
                
                // Show results
                setTimeout(() => {
                    this.displayResults(result);
                    this.showToast('Video analysis completed successfully!', 'success');
                }, 1000);
                
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Analysis failed');
            }

        } catch (error) {
            this.showToast(`Analysis failed: ${error.message}`, 'error');
            this.hideProgressSection();
        } finally {
            this.enableForm();
        }
    }

    /**
     * Upload with progress tracking
     */
    async uploadWithProgress(formData) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const progress = (e.loaded / e.total) * 100;
                    this.updateProgressStep(1, progress);
                }
            });

            // Handle state changes
            xhr.addEventListener('readystatechange', () => {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status === 200) {
                        try {
                            const result = JSON.parse(xhr.responseText);
                            // Video uploaded successfully, now poll for processing status
                            if (result.job_id) {
                                this.updateProgressStep(2, 0);
                                this.pollJobStatus(result.job_id)
                                    .then((finalResult) => resolve({ ok: true, json: () => Promise.resolve(finalResult) }))
                                    .catch(reject);
                            } else {
                                reject(new Error('No job ID received from server'));
                            }
                        } catch (e) {
                            reject(new Error('Invalid response format'));
                        }
                    } else {
                        try {
                            const error = JSON.parse(xhr.responseText);
                            reject(new Error(error.detail || `HTTP ${xhr.status}: ${xhr.statusText}`));
                        } catch (e) {
                            reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
                        }
                    }
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Network error during upload'));
            });

            xhr.open('POST', `${this.apiBaseUrl}/observations/video`);
            xhr.send(formData);
        });
    }

    /**
     * Simulate processing progress for better UX
     */
    async simulateProcessingProgress() {
        // Step 2: Processing
        for (let i = 0; i <= 100; i += 10) {
            this.updateProgressStep(2, i);
            await this.delay(200);
        }

        // Step 3: Analyzing
        for (let i = 0; i <= 100; i += 5) {
            this.updateProgressStep(3, i);
            await this.delay(150);
        }
    }

    /**
     * Poll job status for video processing
     */
    async pollJobStatus(jobId) {
        // Removed timeout limit - will poll indefinitely until completion or genuine error
        while (true) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/observations/video/status/${jobId}`);
                
                if (response.ok) {
                    const status = await response.json();
                    
                    // Update progress based on status
                    if (status.status === 'processing' || status.status === 'processing_frames') {
                        this.updateProgressStep(2, status.progress || 0);
                    } else if (status.status === 'analyzing') {
                        this.updateProgressStep(3, status.progress || 0);
                    }
                      if (status.status === 'completed') {
                        // Processing complete - now fetch insights
                        this.updateProgressStep(3, 100);
                        try {
                            const insightsResponse = await fetch(`${this.apiBaseUrl}/observations/video/${jobId}/insights`);
                            let insights = [];
                            let patterns = [];
                            let summary = '';
                            
                            if (insightsResponse.ok) {
                                const insightsData = await insightsResponse.json();
                                insights = insightsData.key_insights || [];
                                patterns = insightsData.behavior_patterns || [];
                                summary = insightsData.summary || '';
                            }
                            
                            return {
                                success: true,
                                frames_analyzed: status.total_frames || 0,
                                processing_time_ms: status.processing_time_ms || 0,
                                insights: insights,
                                patterns: patterns,
                                summary: summary,
                                analyses: status.frame_analyses || []
                            };
                        } catch (insightsError) {
                            console.warn('Failed to fetch insights:', insightsError);
                            // Return basic results without insights
                            return {
                                success: true,
                                frames_analyzed: status.total_frames || 0,
                                processing_time_ms: status.processing_time_ms || 0,
                                insights: ['Analysis completed successfully'],
                                patterns: ['Basic processing pattern identified'],
                                summary: 'Video analysis completed',
                                analyses: status.frame_analyses || []
                            };
                        }
                    } else if (status.status === 'error') {
                        throw new Error(status.error || 'Processing failed');
                    }
                } else {
                    throw new Error(`Status check failed: ${response.status}`);
                }
                
                // Wait before next poll
                await this.delay(2000);
                
            } catch (error) {
                throw new Error(`Status polling failed: ${error.message}`);
            }
        }
    }

    /**
     * Display analysis results
     */
    displayResults(results) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsContent = document.getElementById('resultsContent');
        
        if (!resultsSection || !resultsContent) return;

        // Show results section
        resultsSection.style.display = 'block';
        
        // Create results HTML
        const resultsHtml = this.generateResultsHTML(results);
        resultsContent.innerHTML = resultsHtml;
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // Store results for export
        this.currentResults = results;
    }

    /**
     * Generate results HTML
     */    generateResultsHTML(results) {
        return `
            <div class="results-grid">
                <div class="result-card">
                    <div class="result-header">
                        <h3><i class="fas fa-info-circle"></i> Analysis Summary</h3>
                    </div>
                    <div class="result-content">
                        <div class="summary-stats">
                            <div class="stat">
                                <span class="stat-label">Processing Time</span>
                                <span class="stat-value">${results.processing_time_ms?.toFixed(1) || 'N/A'}ms</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Frames Analyzed</span>
                                <span class="stat-value">${results.frames_analyzed || 'N/A'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Status</span>
                                <span class="stat-value success">Completed</span>
                            </div>
                        </div>
                        ${results.summary ? `<div class="summary-text"><p>${results.summary}</p></div>` : ''}
                    </div>
                </div>
                
                <div class="result-card">
                    <div class="result-header">
                        <h3><i class="fas fa-eye"></i> Key Insights</h3>
                    </div>
                    <div class="result-content">
                        <div class="insights-list">
                            ${this.generateInsightsList(results.insights || [])}
                        </div>
                    </div>
                </div>
                
                <div class="result-card">
                    <div class="result-header">
                        <h3><i class="fas fa-chart-line"></i> Behavior Patterns</h3>
                    </div>
                    <div class="result-content">
                        <div class="patterns-list">
                            ${this.generatePatternsList(results.patterns || [])}
                        </div>
                    </div>
                </div>
                
                <div class="result-card full-width">
                    <div class="result-header">
                        <h3><i class="fas fa-list"></i> Detailed Analysis</h3>
                    </div>
                    <div class="result-content">
                        <pre class="analysis-details">${JSON.stringify(results, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate insights list HTML
     */
    generateInsightsList(insights) {
        if (!insights.length) {
            return '<p class="no-data">No insights available</p>';
        }
        
        return insights.map(insight => `
            <div class="insight-item">
                <div class="insight-icon">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <div class="insight-text">${insight}</div>
            </div>
        `).join('');
    }    /**
     * Generate patterns list HTML
     */
    generatePatternsList(patterns) {
        if (!patterns.length) {
            return '<p class="no-data">No patterns identified</p>';
        }
        
        return patterns.map(pattern => {
            // Handle both string patterns and object patterns
            if (typeof pattern === 'string') {
                return `
                    <div class="pattern-item">
                        <div class="pattern-name">${pattern}</div>
                    </div>
                `;
            } else {
                return `
                    <div class="pattern-item">
                        <div class="pattern-name">${pattern.name || 'Unknown Pattern'}</div>
                        <div class="pattern-confidence">
                            Confidence: ${((pattern.confidence || 0) * 100).toFixed(1)}%
                        </div>
                    </div>
                `;
            }
        }).join('');
    }

    /**
     * Export results
     */
    exportResults() {
        if (!this.currentResults) {
            this.showToast('No results to export', 'warning');
            return;
        }        const dataStr = JSON.stringify(this.currentResults, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        
        const exportFileDefaultName = `gum-analysis-${new Date().toISOString().split('T')[0]}.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        
        this.showToast('Results exported successfully', 'success');
    }

    /**
     * Start new analysis
     */
    startNewAnalysis() {
        // Reset form
        this.removeSelectedFile();
        
        // Hide results and progress
        const resultsSection = document.getElementById('resultsSection');
        const progressSection = document.getElementById('progressSection');
        
        if (resultsSection) resultsSection.style.display = 'none';
        if (progressSection) progressSection.style.display = 'none';
        
        // Reset progress
        this.currentStep = 1;
        this.uploadProgress = 0;
        this.currentResults = null;
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        this.showToast('Ready for new analysis', 'info');
    }

    /**
     * Handle database cleanup with confirmation
     */
    async handleDatabaseCleanup() {
        // Show confirmation dialog
        const confirmed = confirm(
            'Are you sure you want to clean the entire database?\n\n' +
            'This will permanently delete:\n' +
            '• All observations\n' +
            '• All propositions\n' +
            '• All insights\n' +
            '• All analysis data\n\n' +
            'This action cannot be undone!'
        );

        if (!confirmed) {
            return;
        }

        const cleanupBtn = document.getElementById('cleanupDatabase');
        if (cleanupBtn) {
            cleanupBtn.disabled = true;
            cleanupBtn.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Cleaning...';
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/database/cleanup`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to clean database');
            }

            const result = await response.json();
            
            // Show success message with deletion counts
            const message = `Database cleaned successfully!\n\n` +
                `Deleted:\n` +
                `• ${result.observations_deleted} observations\n` +
                `• ${result.propositions_deleted} propositions\n` +
                `• ${result.junction_records_deleted} junction records\n` +
                `• FTS indexes cleared`;

            this.showToast('Database cleaned successfully!', 'success');
            
            // Optional: Show detailed results in an alert
            alert(message);
            
            // Refresh any displayed data
            this.loadRecentHistory();
            
            // Reset any current results
            this.currentResults = null;
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.style.display = 'none';
            }
            
        } catch (error) {
            console.error('Database cleanup failed:', error);
            this.showToast(`Database cleanup failed: ${error.message}`, 'error');
        } finally {
            // Restore button state
            if (cleanupBtn) {
                cleanupBtn.disabled = false;
                cleanupBtn.innerHTML = '<i class="fas fa-trash" aria-hidden="true"></i> Clean Database';
            }
        }
    }

    /**
     * Hide progress section
     */
    hideProgressSection() {
        const progressSection = document.getElementById('progressSection');
        if (progressSection) {
            progressSection.style.display = 'none';
        }
    }

    /**
     * Disable form during upload
     */
    disableForm() {
        const form = document.getElementById('videoForm');
        if (form) {
            const inputs = form.querySelectorAll('input, button, select');
            inputs.forEach(input => input.disabled = true);
        }
    }

    /**
     * Enable form after upload
     */
    enableForm() {
        const form = document.getElementById('videoForm');
        if (form) {
            const inputs = form.querySelectorAll('input, button, select');
            inputs.forEach(input => input.disabled = false);
        }
        
        // Keep upload button disabled if no file selected
        if (!this.selectedFile) {
            this.disableUploadButton();
        }
    }

    /**
     * Load recent analysis history
     */
    async loadRecentHistory() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/observations?limit=5`);
            if (response.ok) {
                const history = await response.json();
                this.displayHistory(history || []);
            }
        } catch (error) {
            console.warn('Could not load history:', error.message);
        }
    }

    /**
     * Display history
     */
    displayHistory(historyItems) {
        const historyContent = document.getElementById('historyContent');
        if (!historyContent) return;

        if (!historyItems.length) {
            historyContent.innerHTML = '<p class="no-data">No recent analyses found</p>';
            return;
        }

        const historyHtml = historyItems.map(item => `
            <div class="history-item">
                <div class="history-header">
                    <div class="history-title">
                        <i class="fas fa-${item.content_type === 'video' ? 'video' : 'file-alt'}"></i>
                        ${item.content_type === 'video' ? 'Video Analysis' : 'Text Analysis'}
                    </div>
                    <div class="history-date">
                        ${new Date(item.created_at).toLocaleDateString()}
                    </div>
                </div>
                <div class="history-details">
                    <span>Observer: ${item.observer_name || 'Unknown'}</span>
                    <span>Type: ${item.content_type}</span>
                </div>
                <div class="history-content">
                    ${item.content}
                </div>
            </div>
        `).join('');

        historyContent.innerHTML = historyHtml;
    }

    /**
     * Check API connection
     */
    async checkConnection() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`, {
                timeout: 5000
            });
            
            if (response.ok) {
                const health = await response.json();
                this.connectionStatus = health.gum_connected ? 'connected' : 'disconnected';
            } else {
                this.connectionStatus = 'disconnected';
            }
        } catch (error) {
            this.connectionStatus = 'disconnected';
        }
    }

    /**
     * Update connection status display
     */
    updateConnectionStatus() {
        const statusElement = document.getElementById('connectionStatus');
        if (!statusElement) return;

        const statusText = {
            'connected': 'Connected',
            'disconnected': 'Disconnected', 
            'connecting': 'Connecting...'
        };

        // Hide the connection status when connected, only show when there are issues
        if (this.connectionStatus === 'connected') {
            statusElement.style.display = 'none';
        } else {
            statusElement.style.display = 'flex';
            statusElement.className = `connection-status ${this.connectionStatus}`;
            const span = statusElement.querySelector('span');
            if (span) {
                span.textContent = statusText[this.connectionStatus];
            }
        }

        // Show warning if disconnected
        if (this.connectionStatus === 'disconnected') {
            this.showToast('Cannot connect to analysis service. Please check if the controller is running.', 'error');
        }
    }

    /**
     * Update scroll progress
     */
    updateScrollProgress() {
        const scrollTop = document.documentElement.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const progress = (scrollTop / scrollHeight) * 100;
        
        const progressBar = document.getElementById('progressBar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    }    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        if (!toast) return;

        // Clear any existing timeout
        if (this.toastTimeout) {
            clearTimeout(this.toastTimeout);
        }

        // Get icon for toast type
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        // Set toast content with icon
        toast.innerHTML = `
            <i class="${icons[type] || icons.info}" aria-hidden="true"></i>
            <span>${message}</span>
        `;
        
        toast.className = `toast ${type} show`;

        // Auto hide after 6 seconds (longer for better readability)
        this.toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 6000);
    }

    /**
     * Utility: Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Utility: Format duration
     */
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }

    /**
     * Utility: Delay function
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===== PROPOSITIONS FUNCTIONALITY =====

    /**
     * Setup propositions event listeners
     */
    setupPropositionsListeners() {
        const loadPropositionsBtn = document.getElementById('loadPropositions');
        const confidenceFilter = document.getElementById('confidenceFilter');
        const sortBySelect = document.getElementById('sortBy');
        const prevBtn = document.getElementById('prevPropositions');
        const nextBtn = document.getElementById('nextPropositions');

        if (loadPropositionsBtn) {
            loadPropositionsBtn.addEventListener('click', () => {
                this.currentPropositionsPage = 1;
                this.loadPropositions();
            });
        }

        if (confidenceFilter) {
            confidenceFilter.addEventListener('change', () => {
                this.currentPropositionsPage = 1;
                this.loadPropositions();
            });
        }

        if (sortBySelect) {
            sortBySelect.addEventListener('change', () => {
                this.currentPropositionsPage = 1;
                this.loadPropositions();
            });
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentPropositionsPage > 1) {
                    this.currentPropositionsPage--;
                    this.loadPropositions();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.currentPropositionsPage++;
                this.loadPropositions();
            });
        }
    }

    /**
     * Load propositions from the API
     */
    async loadPropositions() {
        const loadBtn = document.getElementById('loadPropositions');
        const contentContainer = document.getElementById('propositionsContent');
        const statsContainer = document.getElementById('propositionsStats');
        const paginationContainer = document.getElementById('propositionsPagination');

        if (!contentContainer) return;

        try {
            // Show loading state
            if (loadBtn) {
                loadBtn.disabled = true;
                loadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
            }

            // Get filter values
            const confidenceMin = document.getElementById('confidenceFilter')?.value || null;
            const sortBy = document.getElementById('sortBy')?.value || 'created_at';
            const limit = 20;
            const offset = (this.currentPropositionsPage - 1) * limit;

            // Build query parameters
            const params = new URLSearchParams({
                limit: limit.toString(),
                offset: offset.toString(),
                sort_by: sortBy
            });

            if (confidenceMin) {
                params.append('confidence_min', confidenceMin);
            }

            // Fetch propositions
            const response = await fetch(`${this.apiBaseUrl}/propositions?${params}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const propositions = await response.json();

            // Fetch count for stats
            const countParams = new URLSearchParams();
            if (confidenceMin) {
                countParams.append('confidence_min', confidenceMin);
            }

            const countResponse = await fetch(`${this.apiBaseUrl}/propositions/count?${countParams}`);
            const countData = await countResponse.json();

            // Display results
            this.displayPropositions(propositions, countData);
            this.updatePropositionsPagination(propositions.length, limit);

            this.showToast(`Loaded ${propositions.length} insights`, 'success');

        } catch (error) {
            console.error('Error loading propositions:', error);
            this.showToast(`Failed to load insights: ${error.message}`, 'error');
            this.displayEmptyPropositions();
        } finally {
            // Reset button state
            if (loadBtn) {
                loadBtn.disabled = false;
                loadBtn.innerHTML = '<i class="fas fa-search"></i> Load Insights';
            }
        }
    }

    /**
     * Display propositions in the UI
     */
    displayPropositions(propositions, countData) {
        const contentContainer = document.getElementById('propositionsContent');
        const statsContainer = document.getElementById('propositionsStats');

        if (!contentContainer) return;

        // Show stats
        if (statsContainer && countData) {
            statsContainer.style.display = 'flex';
            statsContainer.innerHTML = `
                <div class="stat-item">
                    <i class="fas fa-lightbulb"></i>
                    <span>Total: ${countData.total_propositions} insights</span>
                </div>
                <div class="stat-item">
                    <i class="fas fa-filter"></i>
                    <span>Showing: ${propositions.length} results</span>
                </div>
                ${countData.confidence_filter ? `
                    <div class="stat-item">
                        <i class="fas fa-star"></i>
                        <span>Min confidence: ${countData.confidence_filter}</span>
                    </div>
                ` : ''}
            `;
        }

        // Display propositions
        if (propositions.length === 0) {
            this.displayEmptyPropositions();
            return;
        }

        contentContainer.innerHTML = propositions.map((prop, index) => 
            this.createPropositionCard(prop, index)
        ).join('');
    }

    /**
     * Create a proposition card HTML
     */
    createPropositionCard(proposition, index) {
        const confidence = proposition.confidence;
        const confidenceClass = this.getConfidenceClass(confidence);
        const confidenceLabel = this.getConfidenceLabel(confidence);
        
        const createdDate = new Date(proposition.created_at);
        const formattedDate = createdDate.toLocaleDateString() + ' ' + 
                            createdDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        return `
            <div class="proposition-card" style="animation-delay: ${index * 0.1}s">
                <div class="proposition-header">
                    <div class="proposition-meta">
                        <span class="proposition-id">#${proposition.id}</span>
                        <span class="confidence-badge ${confidenceClass}">
                            <i class="fas fa-star"></i>
                            ${confidenceLabel}
                        </span>
                    </div>
                </div>
                
                <div class="proposition-text">
                    ${this.escapeHtml(proposition.text)}
                </div>
                
                ${proposition.reasoning ? `
                    <div class="proposition-reasoning">
                        <strong>Reasoning:</strong> ${this.escapeHtml(proposition.reasoning)}
                    </div>
                ` : ''}
                
                <div class="proposition-footer">
                    <div class="proposition-date">
                        <i class="fas fa-clock"></i>
                        <span>${formattedDate}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Get confidence CSS class
     */
    getConfidenceClass(confidence) {
        if (!confidence) return 'confidence-none';
        if (confidence >= 8) return 'confidence-high';
        if (confidence >= 6) return 'confidence-medium';
        return 'confidence-low';
    }

    /**
     * Get confidence label
     */
    getConfidenceLabel(confidence) {
        if (!confidence) return 'No confidence';
        return `${confidence}/10`;
    }

    /**
     * Display empty state for propositions
     */
    displayEmptyPropositions() {
        const contentContainer = document.getElementById('propositionsContent');
        const statsContainer = document.getElementById('propositionsStats');
        
        if (statsContainer) {
            statsContainer.style.display = 'none';
        }

        if (contentContainer) {
            contentContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-lightbulb"></i>
                    <h3>No insights found</h3>
                    <p>No propositions match your current filters. Try adjusting the confidence level or submit more observations.</p>
                </div>
            `;
        }
    }

    /**
     * Update pagination controls
     */
    updatePropositionsPagination(resultCount, limit) {
        const paginationContainer = document.getElementById('propositionsPagination');
        const prevBtn = document.getElementById('prevPropositions');
        const nextBtn = document.getElementById('nextPropositions');
        const pageInfo = document.getElementById('propositionsPageInfo');

        if (!paginationContainer) return;

        // Show pagination if we have results
        if (resultCount > 0) {
            paginationContainer.style.display = 'flex';
            
            // Update page info
            if (pageInfo) {
                pageInfo.textContent = `Page ${this.currentPropositionsPage}`;
            }

            // Update button states
            if (prevBtn) {
                prevBtn.disabled = this.currentPropositionsPage <= 1;
            }

            if (nextBtn) {
                nextBtn.disabled = resultCount < limit;
            }
        } else {
            paginationContainer.style.display = 'none';
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ===== TAB NAVIGATION FUNCTIONALITY =====

    /**
     * Setup tab navigation event listeners
     */
    setupTabNavigation() {
        const tabButtons = document.querySelectorAll('.tab-button');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tabId = button.getAttribute('data-tab');
                this.switchTab(tabId);
            });
        });
    }

    /**
     * Switch to a specific tab
     */
    switchTab(tabId) {
        // Remove active class from all tabs and panels
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });
        
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });

        // Add active class to selected tab and panel
        const activeButton = document.querySelector(`[data-tab="${tabId}"]`);
        const activePanel = document.getElementById(`${tabId}-panel`);

        if (activeButton && activePanel) {
            activeButton.classList.add('active');
            activeButton.setAttribute('aria-selected', 'true');
            activePanel.classList.add('active');
            this.activeTab = tabId;

            // Load content for specific tabs when activated
            if (tabId === 'analysis') {
                this.loadRecentHistory();
            } else if (tabId === 'insights') {
                // Insights will be loaded when user clicks "Load Insights"
            } else if (tabId === 'query') {
                this.focusQueryInput();
            }
        }
    }

    /**
     * Focus the query input when query tab is activated
     */
    focusQueryInput() {
        const queryInput = document.getElementById('queryInput');
        if (queryInput) {
            setTimeout(() => queryInput.focus(), 100);
        }
    }

    // ===== QUERY FUNCTIONALITY =====

    /**
     * Setup query event listeners
     */
    setupQueryListeners() {
        const queryInput = document.getElementById('queryInput');
        const querySearchBtn = document.getElementById('querySearchBtn');
        const exampleQueries = document.querySelectorAll('.example-query');

        if (queryInput) {
            queryInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.executeQuery();
                }
            });
        }

        if (querySearchBtn) {
            querySearchBtn.addEventListener('click', () => {
                this.executeQuery();
            });
        }

        exampleQueries.forEach(button => {
            button.addEventListener('click', () => {
                const query = button.getAttribute('data-query');
                if (queryInput) {
                    queryInput.value = query;
                    this.executeQuery();
                }
            });
        });
    }

    /**
     * Execute a query against the insights
     */
    async executeQuery() {
        const queryInput = document.getElementById('queryInput');
        const resultsContainer = document.getElementById('queryResults');
        const loadingOverlay = document.getElementById('queryLoading');

        if (!queryInput || !resultsContainer) return;

        const query = queryInput.value.trim();
        if (!query) {
            this.showToast('Please enter a search query', 'warning');
            return;
        }

        try {
            // Show loading state
            if (loadingOverlay) {
                loadingOverlay.style.display = 'flex';
            }

            // Get query parameters
            const limit = document.getElementById('queryLimit')?.value || 10;
            const mode = document.getElementById('queryMode')?.value || 'OR';
            const userName = document.getElementById('queryUserName')?.value || null;

            // Build request
            const requestBody = {
                query: query,
                limit: parseInt(limit),
                mode: mode
            };

            if (userName) {
                requestBody.user_name = userName;
            }

            // Execute query
            const response = await fetch(`${this.apiBaseUrl}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            // Display results
            this.displayQueryResults(result);
            this.showToast(`Found ${result.total_results} insights in ${Math.round(result.execution_time_ms)}ms`, 'success');

        } catch (error) {
            console.error('Query execution failed:', error);
            this.showToast(`Query failed: ${error.message}`, 'error');
            this.displayQueryError(error.message);
        } finally {
            // Hide loading state
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        }
    }

    /**
     * Display query results in the UI
     */
    displayQueryResults(result) {
        const resultsContainer = document.getElementById('queryResults');
        if (!resultsContainer) return;

        if (result.propositions.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <h3>No insights found</h3>
                    <p>No insights match your query "${this.escapeHtml(result.query)}". Try different keywords or broader terms.</p>
                </div>
            `;
            return;
        }

        // Create query stats
        const statsHtml = `
            <div class="query-stats">
                <div class="query-stat">
                    <i class="fas fa-search"></i>
                    <span>Query: "${this.escapeHtml(result.query)}"</span>
                </div>
                <div class="query-stat">
                    <i class="fas fa-chart-bar"></i>
                    <span>${result.total_results} results found</span>
                </div>
                <div class="query-stat">
                    <i class="fas fa-clock"></i>
                    <span>${Math.round(result.execution_time_ms)}ms</span>
                </div>
            </div>
        `;

        // Create results HTML
        const resultsHtml = result.propositions.map((prop, index) => {
            const createdDate = new Date(prop.created_at);
            const formattedDate = createdDate.toLocaleDateString() + ' ' + 
                                createdDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            const confidence = prop.confidence;
            const confidenceClass = this.getConfidenceClass(confidence);
            const confidenceLabel = this.getConfidenceLabel(confidence);

            return `
                <div class="query-result-item" style="animation-delay: ${index * 0.1}s">
                    <div class="query-result-header">
                        <div class="query-result-meta">
                            <span class="result-id">#${prop.id}</span>
                            ${confidence ? `<span class="result-score confidence-${confidenceClass}">${confidenceLabel}</span>` : ''}
                        </div>
                    </div>
                    
                    <div class="query-result-text">
                        ${this.escapeHtml(prop.text)}
                    </div>
                    
                    ${prop.reasoning ? `
                        <div class="query-result-reasoning">
                            <strong>Reasoning:</strong> ${this.escapeHtml(prop.reasoning)}
                        </div>
                    ` : ''}
                    
                    <div class="query-result-footer">
                        <div>
                            <i class="fas fa-clock"></i>
                            <span>${formattedDate}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        resultsContainer.innerHTML = statsHtml + resultsHtml;
    }

    /**
     * Display query error state
     */
    displayQueryError(errorMessage) {
        const resultsContainer = document.getElementById('queryResults');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle" style="color: var(--error-color);"></i>
                <h3>Query Error</h3>
                <p>Failed to execute query: ${this.escapeHtml(errorMessage)}</p>
                <p>Please check your connection and try again.</p>
            </div>
        `;
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.gumApp = new GUMApp();
});

// Add CSS for results display dynamically
const additionalCSS = `
.results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: var(--spacing-lg);
}

.result-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius-lg);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

.result-card.full-width {
    grid-column: 1 / -1;
}

.result-header {
    background: linear-gradient(135deg, var(--primary-color), var(--primary-custom-tooltip-color));
    color: var(--text-white);
    padding: var(--spacing-lg);
}

.result-header h3 {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
}

.result-content {
    padding: var(--spacing-lg);
}

.summary-stats {
    display: grid;
    gap: var(--spacing-md);
}

.stat {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) 0;
    border-bottom: 1px solid var(--border-light);
}

.stat:last-child {
    border-bottom: none;
}

.stat-label {
    color: var(--text-secondary);
    font-weight: 500;
}

.stat-value {
    font-weight: 600;
    color: var(--text-primary);
}

.stat-value.success {
    color: var(--success-color);
}

.insights-list, .patterns-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
}

.insight-item, .pattern-item {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: var(--bg-secondary);
    border-radius: var(--border-radius);
}

.insight-icon {
    color: var(--primary-color);
    font-size: var(--font-size-lg);
    flex-shrink: 0;
}

.insight-text {
    flex: 1;
    color: var(--text-primary);
}

.pattern-name {
    font-weight: 600;
    color: var(--text-primary);
}

.pattern-confidence {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
}

.analysis-details {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: var(--border-radius);
    padding: var(--spacing-lg);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-sm);
    color: var(--text-primary);
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
}

.history-item {
    background: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: var(--border-radius);
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
}

.history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-sm);
}

.history-title {
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
}

.history-date {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
}

.history-details {
    display: flex;
    gap: var(--spacing-lg);
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    margin-bottom: var(--spacing-sm);
}

.history-content {
    font-size: var(--font-size-sm);
    color: var(--text-primary);
    line-height: 1.4;
}

.no-data {
    text-align: center;
    color: var(--text-muted);
    font-style: italic;
    padding: var(--spacing-xl);
}

@media (max-width: 768px) {
    .results-grid {
        grid-template-columns: 1fr;
    }
    
    .history-header {
        flex-direction: column;
        align-items: flex-start;
        gap: var(--spacing-sm);
    }
    
    .history-details {
        flex-direction: column;
        gap: var(--spacing-sm);
    }
}
`;

// Inject additional CSS
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);
