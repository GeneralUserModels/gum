# GUM Module Documentation

## Usage Example

```python
# Create a screen observer
screen_observer = Screen(
    skip_when_visible=["Terminal", "VS Code"],
    model_name="gpt-4-vision-preview"
)

async with gum("system_name", screen_observer) as g:
    # Query the system for screen-related observations
    results = await g.query("user interaction with button", limit=5)
    
    # Example (fake) output of g.query():
    """
    [
        (
            Proposition(
                id=1,
                text="User prefers completing forms in a systematic, top-to-bottom approach",
                reasoning="Multiple observations show consistent pattern of form field interactions followed by submission, with minimal backtracking or corrections",
                confidence=8,
                decay=7,
                created_at="2024-03-20T14:30:45Z",
                updated_at="2024-03-20T14:30:45Z",
                revision_group="abc123",
                version=1
            ),
            0.95
        ),
        (
            Proposition(
                id=2,
                text="User demonstrates high attention to detail in form completion",
                reasoning="Screen captures show careful review of form fields before submission, with consistent pauses at each field and thorough validation",
                confidence=7,
                decay=6,
                created_at="2024-03-20T14:25:12Z",
                updated_at="2024-03-20T14:25:12Z",
                revision_group="def456",
                version=1
            ),
            0.82
        )
    ]
    """
    
    # Register custom update handler for screen observations
    def screen_update_handler(observer, update):
        if isinstance(observer, Screen):
            # Process screen-specific updates
            print(f"New screen observation: {update.content}")
    g.register_update_handler(screen_update_handler)
```

## Core Components

### Main Classes

#### `gum` Class
The main class that orchestrates the entire system.

**Initialization Parameters:**
- `user_name` (str): Name of the user/system
- `*observers` (Observer): Variable number of observer instances
- `propose_prompt` (str, optional): Custom prompt for proposition generation
- `similar_prompt` (str, optional): Custom prompt for similarity analysis
- `revise_prompt` (str, optional): Custom prompt for proposition revision
- `audit_prompt` (str, optional): Custom prompt for auditing
- `data_directory` (str): Directory for storing data (default: "~/.cache/gum")
- `db_name` (str): Name of the database file (default: "gum.db")
- `max_concurrent_updates` (int): Maximum number of concurrent updates (default: 4)
- `verbosity` (int): Logging verbosity level (default: logging.INFO)
- `audit_enabled` (bool): Whether to enable auditing (default: False)

**Key Methods:**

1. `start_update_loop()`
   - Starts the asynchronous update processing loop
   - Manages concurrent processing of updates from observers

2. `stop_update_loop()`
   - Stops the update processing loop
   - Ensures clean shutdown of all processing tasks

3. `connect_db()`
   - Establishes connection to the SQLite database
   - Initializes database if it doesn't exist

4. `query(user_query: str, limit: int = 3, mode: str = "OR", start_time: datetime = None, end_time: datetime = None)`
   - Searches for propositions matching the query
   - Parameters:
     - `user_query`: Search query string
     - `limit`: Maximum number of results (default: 3)
     - `mode`: Search mode ("OR" or "AND")
     - `start_time`: Filter results after this UTC time
     - `end_time`: Filter results before this UTC time
   - Returns: List of tuples containing (Proposition, relevance_score)

5. `add_observer(observer: Observer)`
   - Adds a new observer to the system
   - Observer will start contributing updates to the system

6. `remove_observer(observer: Observer)`
   - Removes an observer from the system
   - Stops processing updates from this observer

7. `register_update_handler(fn: Callable[[Observer, Update], None])`
   - Registers a custom handler for processing updates
   - Allows for custom processing of updates from observers

### Database Models

#### `Observation` Class
Represents an observation in the system.

**Fields:**
- `id`: Unique identifier
- `observer_name`: Name of the observer that created this observation
- `content`: The actual observation content
- `content_type`: Type of the observation content
- `created_at`: Timestamp of creation
- `updated_at`: Timestamp of last update
- `propositions`: Set of related propositions

#### `Proposition` Class
Represents a proposition derived from observations.

**Fields:**
- `id`: Unique identifier
- `text`: The proposition text
- `reasoning`: Reasoning behind the proposition
- `confidence`: Confidence score (optional)
- `decay`: Decay factor (optional)
- `created_at`: Timestamp of creation
- `updated_at`: Timestamp of last update
- `revision_group`: Group identifier for related revisions
- `version`: Version number of the proposition
- `parents`: Set of parent propositions
- `observations`: Set of related observations

### Database Structure and Relationships

The GUM module uses SQLite with SQLAlchemy ORM for data persistence. The database structure consists of several interconnected tables:

#### Core Tables

1. **Observations Table**
   - Primary table for storing observations
   - Contains metadata about the observation source and timing
   - Many-to-many relationship with propositions

2. **Propositions Table**
   - Primary table for storing propositions
   - Contains the proposition text, reasoning, and metadata
   - Many-to-many relationship with observations
   - Self-referential relationship for parent-child connections

3. **Association Tables**
   - `observation_proposition`: Links observations to propositions
   - `proposition_parent`: Links propositions to their parent propositions

4. **FTS5 Virtual Table**
   - `propositions_fts`: Full-text search index for propositions
   - Automatically maintained through triggers
   - Indexes both proposition text and reasoning

#### Proposition Revision Process

The system implements a revision process for propositions:

1. **Initial Proposition Generation**
   ```python
   # When a new observation arrives:
   drafts = await _construct_propositions(update)
   # Each draft gets:
   - Unique revision_group (UUID)
   - Version 1
   - Initial confidence and decay scores
   ```

2. **Similarity Analysis**
   ```python
   # Propositions are categorized into three groups:
   identical, similar, unrel = await _filter_propositions(related_props)
   # Based on relationships:
   - IDENTICAL: Exact matches
   - SIMILAR: Related but different
   - UNRELATED: No significant relationship
   ```

3. **Revision Handling**
   ```python
   # For identical propositions:
   - Attach new observation
   - No revision needed
   
   # For similar propositions:
   - Gather related observations
   - Generate revised propositions
   - Create new version with:
     * Incremented version number
     * New revision_group (if merging different groups)
     * Links to parent propositions
     * Updated confidence/decay scores
   
   # For unrelated propositions:
   - Attach new observation
   - No revision needed
   ```

4. **Version Control**
   - Each proposition has a `version` number
   - Related revisions share a `revision_group`
   - Parent-child relationships track proposition evolution
   - Full history is preserved through the database structure

#### Example Revision Flow

```python
# 1. New observation arrives
observation = Observation(content="User clicked button X")

# 2. Generate initial propositions
drafts = [
    Proposition(
        text="Button X is frequently used",
        reasoning="Based on click frequency",
        version=1,
        revision_group="abc123"
    )
]

# 3. Find similar existing propositions
similar = [
    Proposition(
        text="Button X is important",
        reasoning="Based on usage patterns",
        version=1,
        revision_group="def456"
    )
]

# 4. Generate revised proposition
revised = Proposition(
    text="Button X is both important and frequently used",
    reasoning="Combined evidence from multiple observations",
    version=2,
    revision_group="ghi789",
    parents={drafts[0], similar[0]}
)
```

### Database Utilities

#### `init_db(db_path: str = "gum.db", db_directory: Optional[str] = None)`
- Initializes the SQLite database
- Creates necessary tables and indexes
- Sets up FTS5 virtual table for full-text search
- Returns: Tuple of (engine, Session)

#### `create_fts_table(conn)`
- Creates FTS5 virtual table for full-text search
- Sets up triggers for maintaining the FTS index
- Handles insert, update, and delete operations

### Schemas

The GUM module uses Pydantic models for data validation and serialization. Here are the key schemas:

#### `Update` Schema
Represents an update from an observer.

**Fields:**
- `content` (str): The content of the update
- `content_type` (Literal["input_text", "input_image"]): Type of the update content

#### `PropositionSchema` and `PropositionItem`
Used for proposition generation and validation.

**PropositionItem Fields:**
- `reasoning` (str): The reasoning behind the proposition
- `proposition` (str): The proposition text
- `confidence` (Optional[int]): Confidence score from 1 (low) to 10 (high)
- `decay` (Optional[int]): Decay score from 1 (low) to 10 (high)

**PropositionSchema Fields:**
- `propositions` (List[PropositionItem]): List of up to five propositions

#### `RelationSchema` and `RelationItem`
Used for managing relationships between propositions.

**RelationItem Fields:**
- `source` (int): Source proposition ID
- `label` (Literal["IDENTICAL", "SIMILAR", "UNRELATED"]): Relationship type
- `target` (List[int]): List of target proposition IDs

**RelationSchema Fields:**
- `relations` (List[RelationItem]): List of relationships

#### `AuditSchema`
Used for privacy auditing of updates.

**Fields:**
- `is_new_information` (bool): Whether the message reveals new information
- `data_type` (str): Category of data being disclosed
- `subject` (str): Who the data is about
- `recipient` (str): Who receives the data
- `transmit_data` (bool): Whether downstream processing should continue

### Observers

The GUM module implements an observer pattern for handling updates. The base `Observer` class and a concrete `Screen` observer are provided.

#### Base `Observer` Class
Abstract base class for all observers.

**Key Methods:**
- `__init__(name: Optional[str] = None)`: Initialize observer with optional name
- `get_update()`: Non-blocking method to get an update if available
- `stop()`: Cancel the worker task and drain the queue
- `_worker()`: Abstract method to be implemented by subclasses

#### `Screen` Observer
A concrete observer that captures and processes screen content.

**Initialization Parameters:**
- `screenshots_dir` (str): Directory for storing screenshots (default: "~/.cache/gum/screenshots")
- `skip_when_visible` (Optional[str | list[str]]): Apps to skip when visible
- `transcription_prompt` (Optional[str]): Custom prompt for transcription
- `summary_prompt` (Optional[str]): Custom prompt for summarization
- `model_name` (str): GPT model to use (default: "gpt-4o-mini")
- `history_k` (int): Number of historical frames to keep (default: 10)
- `debug` (bool): Enable debug mode (default: False)

**Features:**
- Captures screenshots before and after user interactions
- Supports periodic captures and event-based captures
- Debounces events to prevent rapid-fire captures
- Maintains a history of recent captures
- Can skip captures when specified applications are visible

**Usage Example:**
```python
# Create a screen observer
screen_observer = Screen(
    skip_when_visible=["Terminal", "VS Code"],
    model_name="gpt-4-vision-preview"
)

# Add to GUM instance
gum_instance.add_observer(screen_observer)
```
