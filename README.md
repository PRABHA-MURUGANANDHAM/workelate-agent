# WorkElate AI Agent

AI agent that plans tasks, remembers decisions, and tracks execution.

## Features
- Plans tasks into 3-5 steps
- Saves decisions to database  
- Shows execution history
- 3-dot delete for history
- Mobile friendly

## Tech Used
- Streamlit (UI)
- LangGraph (planning)
- SQLite (memory)
- Groq Llama 3.1 (AI)

## Quick Start
```bash
pip install -r requirements.txt
streamlit run agent.py
Live Demo
https://workelate-agent-[yourname].streamlit.app

Setup
Add GROQ_API_KEY to Streamlit Secrets

Click test buttons or type tasks

Check sidebar history

File Structure
text
agent.py          - Main app
requirements.txt  - Dependencies
.env.example      - API template
agent_decisions.db - Data (local)
