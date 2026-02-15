import os, sqlite3
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
import operator
from datetime import datetime
import streamlit as st

load_dotenv()
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

DB_PATH = "agent_decisions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, timestamp TEXT, task TEXT, decision TEXT, reasoning TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, task TEXT, plan TEXT, status TEXT)")
    conn.close()

class AgentState(TypedDict):
    input: str
    plan: Annotated[Sequence[str], operator.add]
    decision_trace: list

def save_decision(task: str, decision: str, reasoning: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO decisions (timestamp, task, decision, reasoning) VALUES (?, ?, ?, ?)", 
                (datetime.now().isoformat(), task, decision, reasoning))
    conn.commit()
    conn.close()

def save_full_plan(task: str, plan: list):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO tasks (task, plan, status) VALUES (?, ?, ?)", 
                (task, '|'.join(plan), 'planned'))
    conn.commit()
    conn.close()

def delete_decision(decision_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
    conn.execute("DELETE FROM tasks WHERE task = (SELECT task FROM decisions WHERE id = ?)", (decision_id,))
    conn.commit()
    conn.close()

def get_recent_decisions(task_input: str = None) -> list:
    conn = sqlite3.connect(DB_PATH)
    if task_input:
        cursor = conn.execute("SELECT task, decision, reasoning, timestamp, id FROM decisions WHERE task LIKE ? ORDER BY id DESC LIMIT 5", 
                             (f'%{task_input[:30]}%',))
    else:
        cursor = conn.execute("SELECT task, decision, reasoning, timestamp, id FROM decisions ORDER BY id DESC LIMIT 10")
    decisions = [{"task": row[0], "decision": row[1], "reasoning": row[2], "timestamp": row[3], "id": row[4]} for row in cursor.fetchall()]
    conn.close()
    return decisions

def get_task_plan(task: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT plan FROM tasks WHERE task = ?", (task,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0].split('|')
    return []

def planner(state: AgentState) -> AgentState:
    task = state['input']
    
    prompt = f"""WORKER MODE: Plan this task like a software engineer.

Task: {task}

Return ONLY a clean numbered list of 3-5 actionable steps:
1. 
2. 
3. 
4. 
5. """
    
    plan_text = llm.invoke(prompt).content.strip()
    plan = []
    for line in plan_text.split('\n'):
        line = line.strip()
        if line and line[0].isdigit() and len(line) > 5:
            # Extract CLEAN step text (remove number + dot + extra numbering)
            if '.' in line[:10]:
                parts = line.split('.', 1)
                if len(parts) > 1:
                    step_text = parts[1].strip()
                    if step_text and len(step_text) > 10:  # Meaningful content
                        plan.append(step_text)
            if len(plan) >= 5:
                break
    
    # Ensure minimum 3 clean steps
    while len(plan) < 3:
        plan.append("Review and validate implementation")
    
    reasoning = f"Generated {len(plan)} actionable steps based on task requirements"
    save_decision(task, f"Plan Generated: {len(plan)} steps", reasoning)
    save_full_plan(task, plan)
    
    return {"plan": plan, "decision_trace": [{"decision": "PLANNING COMPLETE", "reasoning": reasoning}]}

# Initialize
init_db()
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("planner", planner)
workflow.set_entry_point("planner")
workflow.add_edge("planner", END)
app = workflow.compile()

# === PERFECT PROFESSIONAL UI ===
st.set_page_config(page_title="WorkElate AI Agent", layout="wide", page_icon="🤖")
st.title("🤖 WorkElate Stateful AI Agent")

# Test buttons ONLY (WorkElate scenarios)
st.subheader("🎯 Quick Test Scenarios")
col1, col2 = st.columns(2)
with col1:
    if st.button("📊 SaaS Dashboard", use_container_width=True):
        st.session_state.new_task = "Launch new SaaS dashboard"
with col2:
    if st.button("👨‍💼 Intern Onboarding", use_container_width=True):
        st.session_state.new_task = "Create onboarding plan for new engineering intern"

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle input
current_task = None
if "new_task" in st.session_state:
    current_task = st.session_state.new_task
    del st.session_state.new_task
else:
    current_task = st.chat_input("Enter your task: ")

if current_task:
    # User message
    with st.chat_message("user"):
        st.markdown(f"**🎯 Task:** {current_task}")
    
    # Agent response
    with st.chat_message("agent"):
        st.markdown("### 📋 **Execution Plan**")
        with st.spinner('🧠 Planning...'):
            result = app.invoke({"input": current_task, "plan": [], "decision_trace": []})
        
        # Perfect CLEAN numbered plan (1,2,3 NOT 1.1,2.2)
        for i, step in enumerate(result['plan'], 1):
            st.markdown(f"**{i}.** {step}")
        
        st.markdown("---")
        
        # Single clean decision
        recent = get_recent_decisions(current_task)
        if recent and len(recent) > 0:
            latest = recent[0]
            with st.expander(f"**{latest['decision']}**", expanded=True):
                st.caption(f"_Task:_ {latest['task'][:50]}...")
                st.caption(f"_Why:_ {latest['reasoning']}")
                st.caption(f"_When:_ {latest['timestamp'][:16]}")
        
        task_plan = get_task_plan(current_task)
        st.success(f"✅ **Plan saved** | {len(task_plan)} steps executed")
    
    st.session_state.messages.append({"role": "assistant", "content": "Task planned successfully"})

# === SIDEBAR WITH 3-DOT DELETE ===
with st.sidebar:
    st.header("📚 Execution History")
    
    all_decisions = get_recent_decisions()
    
    for d in all_decisions[:8]:
        col_menu, col_main = st.columns([0.08, 0.92])
        
        with col_menu:
            if st.button("⋮", key=f"dots_{d['id']}", help="Delete entry"):
                delete_decision(d['id'])
                st.rerun()
        
        with col_main:
            with st.expander(f"⏰ {d['timestamp'][:16]} | {d['task'][:35]}...", expanded=False):
                st.markdown(f"**🎯 {d['decision']}**")
                st.markdown(f"**🧠 {d['reasoning']}**")
                
                if "Plan Generated" in d['decision']:
                    plan_steps = get_task_plan(d['task'])
                    if plan_steps:
                        st.markdown("**📝 Steps:**")
                        for i, step in enumerate(plan_steps, 1):
                            st.caption(f"{i}. {step.strip()}")

st.markdown("---")
st.caption("Powered by Groq Llama 3.1 8B")
