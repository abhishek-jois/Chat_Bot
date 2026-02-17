# Drone Operations Coordinator AI Agent

An AI-powered drone operations management system for Skylark Drones that handles pilot roster management, drone inventory, mission assignments, and conflict detection through a conversational interface.

![Architecture](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20LangChain-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 🚁 Features

### 1. Roster Management
- Query pilot availability by skill, certification, and location
- Calculate total cost for pilots based on mission duration
- View current assignments
- Update pilot status (Available / On Leave / Unavailable) with Google Sheets sync

### 2. Assignment Tracking
- Match pilots to projects based on requirements (skills, certs, budget)
- Match drones to projects based on weather compatibility
- Track active assignments
- Handle reassignments (including urgent ones)

### 3. Drone Inventory
- Query fleet by capability, availability, and location
- Filter drones by weather resistance (IP43 for rainy, Clear Sky Only for generic)
- Track deployment status
- Flag maintenance issues
- Update status with Google Sheets sync

### 4. Conflict Detection
- **Double-booking detection**: Pilot or drone assigned to overlapping projects
- **Skill/certification mismatch warnings**: Assigned resource lacks required qualifications
- **Equipment-pilot location mismatch alerts**: Resources in different locations
- **Budget Overrun Warnings**: Pilot cost exceeds mission budget
- **Weather Risk Alerts**: Non-waterproof drone assigned to rainy mission

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (HTML/JS)                      │
│                   Conversational Chat UI                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   REST API  │  │  AI Agent   │  │  Conflict Detector  │  │
│  │  Endpoints  │  │ (LangChain) │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│         ┌────────────────────────────────────┐               │
│         │        Data Manager                 │               │
│         │  (CSV + Google Sheets Sync)        │               │
│         └──────────────┬─────────────────────┘               │
└────────────────────────┼────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────────┐
    │  CSV    │    │ Google  │    │   OpenAI    │
    │  Files  │    │ Sheets  │    │     API     │
    └─────────┘    └─────────┘    └─────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| `main.py` | FastAPI application with REST endpoints |
| `agent.py` | LangChain-based AI agent with custom tools |
| `data_manager.py` | Handles CSV and Google Sheets data operations |
| `conflict_detector.py` | Validates assignments and detects conflicts |
| `models.py` | Pydantic data models |
| `frontend/index.html` | Single-page chat interface |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key
- (Optional) Google Cloud service account for Sheets sync

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd drone-operations-coordinator
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

5. **Run the server**
   ```bash
   cd backend
   python main.py
   ```

6. **Open the application**
   ```
   http://localhost:8000
   ```

## 🔧 Google Sheets Integration

### Setup Instructions

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project

2. **Enable Google Sheets API**
   - Navigate to APIs & Services > Enable APIs
   - Search for "Google Sheets API" and enable it

3. **Create Service Account**
   - Go to APIs & Services > Credentials
   - Create Service Account
   - Download the JSON key file

4. **Prepare Your Spreadsheet**
   - Create a new Google Spreadsheet
   - Create three sheets named: `pilot_roster`, `drone_fleet`, `missions`
   - Copy headers and data from the CSV files
   - Share the spreadsheet with your service account email (found in the JSON key)

5. **Configure Environment**
   ```bash
   USE_GOOGLE_SHEETS=true
   GOOGLE_SPREADSHEET_ID=your_spreadsheet_id_from_url
   GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
   # OR for deployment:
   GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
   ```

## 📡 API Endpoints

### Chat
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Main conversational endpoint |

### Pilots
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pilots` | GET | Get all pilots (with filters) |
| `/api/pilots/{id}` | GET | Get specific pilot |
| `/api/pilots/{id}/status` | PUT | Update pilot status |
| `/api/pilots/{id}/cost/{mission_id}` | GET | Calculate pilot cost |

### Drones
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/drones` | GET | Get all drones (with filters) |
| `/api/drones/{id}` | GET | Get specific drone |
| `/api/drones/{id}/status` | PUT | Update drone status |
| `/api/drones/maintenance/upcoming` | GET | Get drones needing maintenance |

### Missions
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/missions` | GET | Get all missions |
| `/api/missions/{id}` | GET | Get specific mission |
| `/api/missions/{id}/suitable-pilots` | GET | Find suitable pilots |
| `/api/missions/{id}/suitable-drones` | GET | Find suitable drones |

### Assignments
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/assignments` | POST | Create assignment |
| `/api/assignments/{mission_id}` | DELETE | Remove assignment |

### Conflicts
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/conflicts` | GET | Check all conflicts |
| `/api/conflicts/validate` | POST | Validate potential assignment |

## 💬 Example Conversations

```
User: "Show me available pilots in Bangalore"
Agent: Lists pilots with Available status in Bangalore

User: "Find suitable pilots for PRJ001"
Agent: Analyzes requirements and returns ranked pilot recommendations

User: "Assign pilot P001 and drone D001 to PRJ001"
Agent: Validates for conflicts, warns about budget overrun, makes assignment

User: "What conflicts exist in the system?"
Agent: Returns comprehensive conflict report with errors, warnings, info

User: "Urgent reassignment needed for PRJ002 - pilot is sick"
Agent: Handles reassignment - unassigns current, finds alternatives, reassigns
```

## 🚀 Deployment

### Railway

1. Connect your GitHub repository
2. Set environment variables in Railway dashboard
3. Deploy automatically

### Render

1. Create a new Web Service
2. Connect your repository
3. Set environment variables
4. Build command: `pip install -r requirements.txt`
5. Start command: `cd backend && python main.py`

### Replit

1. Import from GitHub
2. Add Secrets (environment variables)
3. Run the application

### Docker

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "backend/main.py"]
```

## 📊 Data Schema

### Pilot Roster
| Field | Type | Description |
|-------|------|-------------|
| pilot_id | string | Unique identifier (P001, P002...) |
| name | string | Pilot name |
| skills | list | Mapping, Survey, Inspection, Thermal |
| certifications | list | DGCA, Night Ops |
| location | string | Current location |
| status | enum | Available, Assigned, On Leave, Unavailable |
| current_assignment | string | Assigned project ID |
| available_from | date | Date when available |
| daily_rate_inr | int | Daily rate in INR |

### Drone Fleet
| Field | Type | Description |
|-------|------|-------------|
| drone_id | string | Unique identifier (D001, D002...) |
| model | string | Drone model |
| capabilities | list | RGB, LiDAR, Thermal |
| status | enum | Available, Deployed, Maintenance |
| location | string | Current location |
| current_assignment | string | Assigned project ID |
| maintenance_due | date | Next maintenance date |
| weather_resistance | string | IP43 (Rain) or None (Clear Sky Only) |

### Missions
| Field | Type | Description |
|-------|------|-------------|
| project_id | string | Unique identifier (PRJ001...) |
| client | string | Client name |
| location | string | Mission location |
| required_skills | list | Required pilot skills |
| required_certs | list | Required certifications |
| start_date | date | Mission start |
| end_date | date | Mission end |
| priority | enum | Urgent, High, Standard |
| mission_budget_inr | int | Budget in INR |
| weather_forecast | string | Sunny, Cloudy, Rainy |

## 🧪 Testing

```bash
# Run the server
cd backend && python main.py

# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me all pilots"}'
```

## 📝 License

MIT License - feel free to use and modify as needed.

---

Built with ❤️ for Skylark Drones
