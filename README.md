# Story Nest

A web-based story publishing and reading platform built with Flask, PostgreSQL, and PL/pgSQL.

## Features

- User authentication (Reader/Author/Admin roles)
- Story creation and publishing
- Chapter management
- Rating and commenting system
- Reading list
- Author dashboard with analytics
- Admin moderation panel
- Notifications system

## Technology Stack

- Frontend: HTML5, CSS3
- Backend: Python (Flask)
- Database: PostgreSQL with PL/pgSQL

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL 12+

### Installation

1. Install dependencies:
```
pip install flask psycopg2-binary werkzeug
```

2. Create PostgreSQL database:
```
createdb story_nest
```

3. Configure database connection in `config.py`

4. Initialize database:
```
psql -d story_nest -f db/schema.sql
psql -d story_nest -f db/functions.sql
psql -d story_nest -f db/triggers.sql
```

5. Run the application:
```
python app.py
```

6. Access at: http://localhost:5000

## Project Structure

```
story_nest/
├── app.py                 # Main application
├── config.py              # Configuration
├── templates/             # HTML templates
├── static/                # CSS files
├── db/                    # Database scripts
└── README.md
```

## Default Roles

- Reader: Read, comment, rate stories
- Author: Reader permissions + create/publish stories
- Admin: Full access to moderation and user management
