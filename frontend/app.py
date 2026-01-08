import streamlit as st
import streamlit_shadcn_ui as ui
import requests
import json
import os
import time

# Configuration
# Point to backend (Render URL in prod, localhost in dev)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

st.set_page_config(
    page_title="Enterprise RAG", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Premium Look ---
st.markdown("""
<style>
    /* Global Gradient Background */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #e2e8f0;
    }
    
    /* Smooth Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #0f172a; 
    }
    ::-webkit-scrollbar-thumb {
        background: #334155; 
        border-radius: 5px;
    }

    /* Glassmorphism for Containers */
    .stChatMessage {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        animation: fadeIn 0.5s ease-in-out;
    }
    
    /* Input Box Styling */
    .stChatInputContainer textarea {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
        border-radius: 12px !important;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Typography */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.025em;
    }
    
    /* Sidebar Polish */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("⚡ Enterprise RAG")
    st.caption("v1.0.0 | Powered by Phi-3 & FAISS")
    
    st.markdown("---")
    
    st.markdown("### ⚙️ Engine Settings")
    alpha = ui.slider(default_value=[0.5], min_value=0.0, max_value=1.0, step=0.1, label="Hybrid Alpha (Keyword ↔ Semantic)", key="alpha_slider")
    top_k = ui.slider(default_value=[5], min_value=1, max_value=10, step=1, label="Retrieval Depth (Top-K)", key="top_k_slider")
    
    use_expansion = ui.switch(default_checked=True, label="Query Expansion (AI)", key="qe_switch")
    
    st.markdown("---")
    
    # Session Stats
    st.markdown("### 📊 Session Stats")
    if "request_count" not in st.session_state:
        st.session_state.request_count = 0
    
    ui.metric_card(title="Total Queries", content=f"{st.session_state.request_count}", description="In this session", key="stats_card")
    
    if st.button("🗑️ Clear History", type="secondary"):
        st.session_state.messages = []
        st.rerun()

# --- Main Interface ---

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.title("Knowledge Assistant")
    st.markdown("Ask anything about your enterprise documents. The system uses **Hybrid Search** and **Cross-Encoder Reranking** for maximum accuracy.")
with col2:
    # Just a visual spacer or logo could go here
    pass

# Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])
        if "sources" in message:
             with st.expander(f"📚 View {len(message['sources'])} Retrieved Sources"):
                 for idx, source in enumerate(message["sources"]):
                     ui.card(title=f"Source {idx+1}", content=source.get('content', '')[:300] + "...", description=f"ID: {source.get('id', 'unknown')}", key=f"src_{message.get('timestamp')}_{idx}")

# Input Processing
if prompt := st.chat_input("What would you like to know?"):
    # User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # Assistant Response
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        
        # Loader
        with st.spinner("Thinking... (Searching Vector DB & Generating Answer)"):
            try:
                # Prepare Payload
                # Shadcn slider returns list, need to extract value
                alpha_val = alpha[0] if isinstance(alpha, list) else alpha
                top_k_val = top_k[0] if isinstance(top_k, list) else top_k
                
                payload = {
                    "query": prompt,
                    "top_k": int(top_k_val),
                    "alpha": float(alpha_val),
                    "use_query_expansion": use_expansion
                }
                
                start_time = time.time()
                
                # --- Authenticate first (Auto-Login) ---
                # Ideally this would be a login screen, but for this demo we auto-login as admin
                auth_data = {
                    "username": "admin",
                    "password": "password"
                }
                
                # 1. Get Token
                token_response = requests.post(f"{BACKEND_URL.replace('/api/v1', '')}/api/v1/token", data=auth_data)
                
                if token_response.status_code != 200:
                     st.error("Authentication Failed. Check backend logs.")
                     st.stop()
                     
                token = token_response.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                # 2. Query RAG
                response = requests.post(
                    f"{BACKEND_URL}/rag/query", 
                    json=payload,
                    headers=headers
                )
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    sources = data["sources"]
                    warning = data.get("warning")
                    
                    full_response = answer
                    if warning:
                        full_response += f"\n\n**⚠️ Note**: {warning}"
                    
                    # Add stats footer
                    stats_footer = f"\n\n*⏱️ Latency: {elapsed:.2f}s | 📄 Sources: {len(sources)}*"
                    message_placeholder.markdown(full_response + stats_footer)
                    
                    # Update Session State
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": full_response + stats_footer,
                        "sources": sources,
                        "timestamp": time.time()
                    })
                    st.session_state.request_count += 1
                    
                    # Show sources immediately in a nice way
                    with st.expander(f"📚 View {len(sources)} Retrieved Sources"):
                         for idx, source in enumerate(sources):
                             st.info(f"**Source {idx+1}**: {source.get('content', '')[:300]}...")
                             
                else:
                    error_msg = f"❌ Error {response.status_code}: {response.text}"
                    message_placeholder.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
            except Exception as e:
                message_placeholder.error(f"🔌 Connection Error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Connection Error: {e}"})
                
# Footer
st.markdown("---")
st.markdown("<center><small>Enterprise RAG Platform | Deployed on Render & HF Spaces</small></center>", unsafe_allow_html=True)
