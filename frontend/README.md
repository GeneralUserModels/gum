# GUM Frontend Web Interface

A modern, responsive web interface for interacting with the GUM (General User Models) REST API. This frontend allows users to submit observations, query insights, and view observation history through an intuitive web interface.

## Features

### Submit Observations
- **Text Observations**: Enter behavioral observations directly through a form
- **Image Observations**: Upload images for AI analysis and insight generation
- **Drag & Drop**: Easy file upload with drag and drop support
- **Real-time Preview**: Preview uploaded images before submission

### Query Insights
- **Natural Language Search**: Query behavioral insights using natural language
- **Configurable Results**: Adjust the number of results returned
- **Rich Results Display**: View propositions with confidence scores and reasoning
- **User-specific Queries**: Query insights for specific users

### Observation History
- **Recent Observations**: View recently submitted observations
- **Pagination**: Load different numbers of historical records
- **Detailed View**: See observation content, type, and metadata
- **User Filtering**: Filter observations by user

### Modern UI/UX
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark/Light Theme**: Beautiful gradient design with modern aesthetics
- **Real-time Feedback**: Toast notifications for all actions
- **Loading States**: Visual feedback during API calls
- **Connection Status**: Real-time API connection monitoring

## Directory Structure

```
frontend/
├── index.html              # Main HTML file
├── server.py              # Simple Python HTTP server
├── README.md              # This file
└── static/
    ├── css/
    │   └── styles.css     # Main stylesheet
    ├── js/
    │   └── app.js         # JavaScript application
    └── images/            # Image assets (if any)
```

## Setup & Installation

### Prerequisites
- GUM API Controller running (usually on port 8001)
- Python 3.6+ (for the simple server)
- Modern web browser

### Quick Start

1. **Start the GUM API Controller** (in the main GUM directory):
   ```bash
   cd /path/to/gum
   python controller.py --port 8001
   ```

2. **Start the Frontend Server**:
   ```bash
   cd frontend
   python server.py
   ```

3. **Open in Browser**:
   - Navigate to http://localhost:3000
   - The interface should automatically detect the API connection

### Alternative Server Options

#### Using Python's built-in server:
```bash
cd frontend
python -m http.server 3000
```

#### Using any other static server:
Just serve the `frontend/` directory as static files on any port.

## Configuration

### API Endpoint
The frontend automatically loads the API base URL from the environment configuration. To change this:

1. **Recommended**: Edit `frontend/.env` file:
   ```env
   # GUM Frontend Configuration
   BACKEND_ADDRESS=http://localhost:8002
   ```

2. **Alternative**: Set environment variable:
   ```bash
   export BACKEND_ADDRESS=http://your-api-host:port
   python server.py
   ```

3. **Legacy**: Directly edit `frontend/static/js/app.js` (not recommended):
   ```javascript
   constructor() {
       this.apiBaseUrl = 'http://your-api-host:port';
       // ...
   }
   ```

The server will automatically inject the configured API URL into the frontend when serving `index.html`.

### Server Port
To run the frontend server on a different port:
```bash
python server.py --port 8080
```

## Usage Guide

### Submitting Text Observations
1. Click on the "Submit Observations" tab
2. In the "Submit Text Observation" section:
   - Enter your observation in the text area
   - Optionally specify a user name
   - Optionally change the observer name
   - Click "Submit Text Observation"

### Submitting Image Observations
1. In the "Submit Image Observation" section:
   - Click the upload area or drag and drop an image
   - Optionally specify a user name
   - Click "Submit Image Observation"
   - The image will be analyzed by AI and processed

### Querying Insights
1. Click on the "Query Insights" tab
2. Enter your search query (e.g., "productivity patterns", "coding habits")
3. Optionally specify a user name and result limit
4. Click "Search Insights"
5. View the results with confidence scores and reasoning

### Viewing History
1. Click on the "History" tab
2. Optionally specify a user name and number of records
3. Click "Load History"
4. Browse through recent observations

## Example Workflows

### Adding Development Observations
```
1. Submit text: "User spent 2 hours coding in VS Code with multiple files open"
2. Submit image: Upload a screenshot of your development environment
3. Query: "development workflow" to see generated insights
```

### Analyzing Productivity Patterns
```
1. Submit multiple observations about work activities
2. Query: "productivity patterns" or "work efficiency"
3. Review insights to understand behavioral patterns
```

### Team Usage Tracking
```
1. Submit observations with different user names
2. Query insights for specific team members
3. Compare patterns across different users
```

## Features in Detail

### Connection Status Indicator
- **Green (Connected)**: API is reachable and healthy
- **Red (Disconnected)**: Cannot reach the API
- **Yellow (Connecting)**: Checking connection status

### Toast Notifications
- **Success (Green)**: Operations completed successfully
- **Error (Red)**: Issues with operations or API calls
- **Info (Blue)**: General information messages

### Loading States
- **Loading Overlay**: Shown during long operations (AI analysis)
- **Disabled Buttons**: Prevent multiple submissions during processing
- **Progress Feedback**: Processing time displayed after completion

### File Upload
- **Drag & Drop**: Drag images directly onto the upload area
- **File Validation**: Only image files are accepted
- **Preview**: See selected image before submission
- **Size Handling**: Large images are automatically resized

## Development

### Adding New Features
1. **HTML**: Add new elements to `index.html`
2. **CSS**: Style elements in `static/css/styles.css`
3. **JavaScript**: Add functionality in `static/js/app.js`


### API Integration
All API calls are handled in the `GUMApp` class methods:
- `submitTextObservation()`
- `submitImageObservation()`
- `queryInsights()`
- `loadHistory()`

## Troubleshooting

### "Cannot connect to GUM API"
- Ensure the GUM API controller is running on port 8001
- Check that both frontend and API are on the same network
- Verify firewall settings aren't blocking connections

### Images not uploading
- Check file size (very large images may timeout)
- Ensure file is a valid image format
- Check browser console for error messages

### Queries returning no results
- Try broader search terms
- Ensure observations have been submitted and processed
- Check that you're querying the correct user name

### Frontend not loading
- Ensure you're accessing the correct URL (http://localhost:3000)
- Check browser console for JavaScript errors
- Verify all static files are being served correctly

## Security Considerations
### Privacy
- All data is processed locally through your GUM instance
- Images are sent to Azure OpenAI for analysis (per GUM configuration)
- No data is stored by the frontend itself

