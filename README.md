# Zubin AI - powered by ROMA 

An AI platform powered by ROMA framework to solve real-life problems, with a specialized focus on Polymarket prediction market analysis.

##  Overview

This project provides an intelligent agent system that can:
- Answer questions about Polymarket prediction markets in real-time
- Analyze trending markets and trading volumes
- Track market liquidity and holder positions
- Provide comprehensive market insights with current data

**Key Features:**
-  Real-time Polymarket market data
-  AI-powered natural language queries
-  RESTful API for easy integration
-  Production-ready Docker deployment
-  Built on ROMA's robust multi-agent framework

---

##  Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **Git**
- **Just** (command runner) - Install with: `cargo install just` or `brew install just`

**System Requirements:**
- 8GB+ RAM recommended
- 20GB+ free disk space
- Linux/MacOS (Windows with WSL2)

---

##  Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Iziedking/zubin-ai.git
cd zubin-ai/ROMA_backend/ROMA-izie_v2
```

### 2. Environment Setup

Create your `.env` file:

```bash
cp .env.example .env
```

**Required Environment Variables:**

```bash
# openrouter API (Required)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: The Graph API for on-chain Polymarket data
GRAPH_API_KEY=your_graph_api_key_here
```

**Get API Keys:**
- **open router API Key**: https://openrouter.ai/settings/keys
- **The Graph API Key** (optional): https://thegraph.com/studio/

### 3. Build and Start

```bash
# Build and start all services
just docker-up-full

# Or step by step:
just docker-build      # Build containers
just docker-up         # Start services
```

**Services will be available at:**
- **ROMA API**: http://localhost:8000
- **MLflow UI**: http://localhost:5000
- **PostgreSQL**: localhost:5432

### 4. Verify Installation

```bash
# Check if services are running
docker ps

# Test the API
curl http://localhost:8000/health
```

---

##  Using the Polymarket Agent

### CLI Usage

The easiest way to test the Polymarket agent:

```bash
just solve "What are the top 5 trending markets on Polymarket?" crypto_agent 3 false text
```

**Command Structure:**
```bash
just solve "YOUR_QUESTION" crypto_agent 3 false text
           └─ Query        └─ Profile  │  │    └─ Output format
                                        │  └─ Verbose (true/false)
                                        └─ Max depth (task decomposition)
```

### Example Queries

```bash
# Trending markets
just solve "What are the current trending markets on Polymarket?" crypto_agent 3 false text

# Search for specific markets
just solve "Find Bitcoin-related prediction markets on Polymarket" crypto_agent 3 false text

# Market details
just solve "What is the trading volume for US recession 2025 market?" crypto_agent 3 false text

# Liquid markets
just solve "Show me the most liquid Polymarket markets" crypto_agent 3 false text
```

---

## API Integration

### REST API Endpoint

**Endpoint:** `POST http://localhost:8000/api/v1/solve`

**Request Body:**
```json
{
  "task": "What are the top 5 trending markets on Polymarket?",
  "profile": "crypto_agent",
  "max_depth": 3,
  "verbose": false
}
```

**Response:**
```json
{
  "status": "success",
  "result": "Detailed AI-generated response with market data...",
  "execution_id": "uuid-here",
  "execution_time": 25.3
}
```

### Example: cURL

```bash
curl -X POST http://localhost:8000/api/v1/solve \
  -H "Content-Type: application/json" \
  -d '{
    "task": "What are the trending Polymarket markets?",
    "profile": "crypto_agent",
    "max_depth": 3,
    "verbose": false
  }'
```

### Example: JavaScript/TypeScript

```typescript
async function queryPolymarket(question: string) {
  const response = await fetch('http://localhost:8000/api/v1/solve', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      task: question,
      profile: 'crypto_agent',
      max_depth: 3,
      verbose: false
    })
  });
  
  const data = await response.json();
  return data.result;
}

// Usage
const result = await queryPolymarket("What are the top Polymarket markets?");
console.log(result);
```

### Example: Python

```python
import requests

def query_polymarket(question: str) -> str:
    response = requests.post(
        'http://localhost:8000/api/v1/solve',
        json={
            'task': question,
            'profile': 'crypto_agent',
            'max_depth': 3,
            'verbose': False
        }
    )
    return response.json()['result']

# Usage
result = query_polymarket("What are the trending Polymarket markets?")
print(result)
```

---

## Project Structure

```
zubin-ai/
├── ROMA_backend/
│   └── ROMA-izie_v2/
│       ├── src/
│       │   └── roma_dspy/
│       │       ├── tools/
│       │       │   └── crypto/
│       │       │       └── polymarket/
│       │       │           ├── __init__.py
│       │       │           ├── toolkit.py      # Polymarket agent logic
│       │       │           ├── client.py       # API client
│       │       │           └── types.py        # Type definitions
│       │       ├── core/                       # ROMA core framework
│       │       └── config/                     # Configuration files
│       ├── docker-compose.yml                  # Docker services
│       ├── Dockerfile                          # Container definition
│       ├── justfile                            # Command shortcuts
│       └── .env                                # Environment variables
└── zubin-ai/                                   # Complete build files
```

---

##  Available Commands (Justfile)

```bash
# Docker Management
just docker-build         # Build Docker containers
just docker-up            # Start services
just docker-down          # Stop services
just docker-up-full       # Build and start (complete setup)
just docker-build-clean   # Clean rebuild

# Agent Interaction
just solve "question" profile depth verbose format
# Example: just solve "trending markets?" crypto_agent 3 false text

# Logs and Debugging
just logs                 # View all logs
just logs-api             # View API logs only
docker logs -f roma-dspy-api

# Database
just db-shell            # Access PostgreSQL shell
just db-reset            # Reset database (caution!)

# MLflow (Experiment Tracking)
# Access at: http://localhost:5000
```

---

##  Configuration

### Agent Profiles

Edit `config/profiles/crypto_agent.yaml` to customize:

```yaml
agent_config:
  name: "Polymarket Crypto Agent"
  description: "Specialized agent for Polymarket data"
  
toolkits:
  - name: PolymarketToolkit
    enabled: true
    config:
      timeout: 30
      cache_ttl: 300
```

### Polymarket Toolkit Configuration

Location: `src/roma_dspy/tools/crypto/polymarket/toolkit.py`

**Features:**
-  Real-time market data from Polymarket Gamma API
-  Automatic filtering of closed/expired markets
-  Date validation to ensure only active markets
-  6 specialized tools for market analysis

**Available Tools:**
1. `search_markets` - Search by keyword
2. `get_trending_markets` - Get top markets by 24h volume
3. `get_liquid_markets` - Get highest liquidity markets
4. `get_market_details` - Detailed market information
5. `get_user_positions` - User portfolio tracking
6. `get_market_holders` - Top holder analysis

---

##  Monitoring and Observability

### MLflow Dashboard

Access experiment tracking at: **http://localhost:5000**

Features:
- Execution traces
- Performance metrics
- Tool usage statistics
- Model parameters

### PostgreSQL Database

Connection details:
```
Host: localhost
Port: 5432
Database: roma
User: roma
Password: (from .env)
```

Access shell:
```bash
just db-shell
```

---

##  Troubleshooting

### Common Issues

**1. Docker containers won't start**
```bash
# Check if ports are already in use
lsof -i :8000
lsof -i :5000
lsof -i :5432

# Clean rebuild
just docker-down
docker system prune -a
just docker-build-clean
just docker-up-full
```

**2. API returns old/closed markets**
- Ensure you're using the latest `toolkit.py` and `client.py`
- Check that `closed=false` parameter is in API calls
- Verify date filtering is active

**3. Missing environment variables**
```bash
# Check .env file exists
cat .env | grep OPENROUTER_API_KEY

# Restart after adding keys
just docker-down
just docker-up
```

**4. Connection errors**
```bash
# Check service health
curl http://localhost:8000/health

# View logs
docker logs roma-dspy-api
docker logs roma-postgres
docker logs roma-mlflow
```

**5. Permission denied errors**
```bash
# Fix file permissions
chmod +x justfile
sudo chown -R $USER:$USER .
```

---

##  Testing

```bash
# Test basic query
just solve "test query" crypto_agent 3 false text

# Test Polymarket integration
just solve "What are the trending markets on Polymarket?" crypto_agent 3 false text

# Test with verbose logging
just solve "Find Bitcoin markets" crypto_agent 3 true text
```

---

##  Additional Resources

- **ROMA Framework**: [Documentation](https://github.com/sentient-agi/ROMA)
- **Polymarket API**: https://docs.polymarket.com

---

##  Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

##  Acknowledgments

- Built on the **ROMA Framework** for multi-agent orchestration
- Powered by **openrouter** for AI reasoning
- **Polymarket** for real-time prediction market data
- **The Graph** for on-chain blockchain data

---

##  Contact

**Project Maintainer**: [Iziedking](https://x.com/Iziedking)  
**GitHub**: [Iziedking](https://github.com/Iziedking)

For issues and questions, please use [GitHub Issues](https://github.com/Iziedking/zubin-ai/issues).


**Last Updated**: October 2025  
**Version**: 1.0.0
