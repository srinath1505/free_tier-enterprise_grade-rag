import streamlit as st
import streamlit_shadcn_ui as ui
import requests
import json
import os
import time
import pandas as pd

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

# Use wide layout
st.set_page_config(
    page_title="Enterprise RAG Portal", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #e2e8f0; }
    .stChatMessage { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; }
    .stTextInput input { background-color: #1e293b !important; color: #f8fafc !important; border-radius: 8px !important; }
    section[data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #334155; }
    div[data-testid="stExpander"] { background-color: transparent; border: 1px solid #334155; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if "token" not in st.session_state: st.session_state.token = None
if "role" not in st.session_state: st.session_state.role = None
if "username" not in st.session_state: st.session_state.username = None
if "messages" not in st.session_state: st.session_state.messages = []
if "request_count" not in st.session_state: st.session_state.request_count = 0

# --- Authentication Views ---

def login_register_view():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Enterprise Access")
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary")
                
                if submitted:
                    try:
                        # Ensure backend URL is base
                        token_url = f"{BACKEND_URL}/token"
                        # Handle potential double slash if BACKEND_URL ends with /api/v1
                        if "api/v1/api/v1" in token_url: token_url = token_url.replace("api/v1/api/v1", "api/v1")

                        res = requests.post(token_url, data={"username": username, "password": password})
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.token = data["access_token"]
                            # Decode token to get role (naive decode for demo, or fetch /me)
                            # We'll just assume role based on username/response or fetch via new endpoint
                            # ideally /me endpoint, but for now we trust the login flow.
                            # Let's decode or simply re-request or store role in response?
                            # Our backend only returns token. Let's add role to return or decode JWT.
                            # Quick hack: We know admin is admin.
                            st.session_state.username = username
                            if username == "admin": 
                                st.session_state.role = "admin" 
                            else: 
                                st.session_state.role = "viewer"
                            st.success("Login Successful!")
                            st.rerun()
                        else:
                            st.error(f"Login Failed: {res.text}")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")

        with tab2:
            with st.form("reg_form"):
                new_user = st.text_input("New Username")
                new_pass = st.text_input("New Password", type="password")
                reg_submitted = st.form_submit_button("Create Account")
                
                if reg_submitted:
                    try:
                        reg_url = f"{BACKEND_URL}/register"
                        # Handle potential double slash
                        if "api/v1/api/v1" in reg_url: reg_url = reg_url.replace("api/v1/api/v1", "api/v1")

                        res = requests.post(reg_url, json={"username": new_user, "password": new_pass})
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.token = data["access_token"]
                            st.session_state.username = new_user
                            st.session_state.role = "viewer"
                            st.success("Account Created!")
                            st.rerun()
                        else:
                            st.error(f"Registration Failed: {res.text}")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")

# --- Application Views ---

def sidebar():
    with st.sidebar:
        st.title("⚡ Enterprise RAG")
        st.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.role})")
        
        if st.button("Logout", type="secondary"):
            st.session_state.token = None
            st.session_state.role = None
            st.session_state.messages = []
            st.rerun()
            
        st.divider()
        st.markdown("### ⚙️ Settings")
        alpha = ui.slider(default_value=[0.5], min_value=0.0, max_value=1.0, step=0.1, label="Hybrid Search Alpha", key="alpha_slider")
        top_k = ui.slider(default_value=[5], min_value=1, max_value=10, step=1, label="Retrieval Depth", key="top_k_slider")
        use_expansion = ui.switch(default_checked=True, label="Query Expansion", key="qe_switch")
        
        return alpha, top_k, use_expansion

def chat_interface(alpha, top_k, use_expansion):
    st.markdown("## 💬 Knowledge Assistant")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
            st.markdown(message["content"])
            if "sources" in message:
                with st.expander(f"📚 View {len(message['sources'])} Sources"):
                    for idx, source in enumerate(message["sources"]):
                        st.caption(f"**Source {idx+1}**: {source.get('content', '')[:300]}...")

    if prompt := st.chat_input("Ask a question about your documents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            with st.spinner("Searching Vector Database..."):
                try:
                    alpha_val = alpha[0] if isinstance(alpha, list) else alpha
                    top_k_val = top_k[0] if isinstance(top_k, list) else top_k
                    
                    payload = {
                        "query": prompt, "top_k": int(top_k_val), "alpha": float(alpha_val), "use_query_expansion": use_expansion
                    }
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    
                    rag_url = f"{BACKEND_URL}/rag/query"
                    if "api/v1/api/v1" in rag_url: rag_url = rag_url.replace("api/v1/api/v1", "api/v1")
                    
                    res = requests.post(rag_url, json=payload, headers=headers)
                    
                    if res.status_code == 200:
                        data = res.json()
                        full_res = data["answer"]
                        if data.get("warning"): full_res += f"\n\n**⚠️ Note**: {data['warning']}"
                        
                        placeholder.markdown(full_res)
                        st.session_state.messages.append({
                            "role": "assistant", "content": full_res, "sources": data["sources"]
                        })
                        
                        with st.expander("📚 Sources Cited"):
                            for s in data["sources"]:
                                st.info(s.get('content', '')[:300] + "...")
                    else:
                        err = f"❌ Error {res.status_code}: {res.text}"
                        placeholder.error(err)
                        st.session_state.messages.append({"role": "assistant", "content": err})
                        
                except Exception as e:
                    placeholder.error(f"Error: {e}")

def knowledge_base_interface():
    st.markdown("## 📂 Knowledge Base Management")
    st.info("Upload documents to ingest them immediately into the Vector Database.")
    
    # Upload
    uploaded_file = st.file_uploader("Upload Document (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"])
    if uploaded_file:
        if st.button("🚀 Upload & Ingest"):
            with st.spinner("Uploading and Processing..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    
                    upload_url = f"{BACKEND_URL}/ingest/upload"
                    if "api/v1/api/v1" in upload_url: upload_url = upload_url.replace("api/v1/api/v1", "api/v1")
                    
                    res = requests.post(upload_url, files=files, headers=headers)
                    if res.status_code == 200:
                        st.success(f"Success! {res.json()['message']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Upload Failed: {res.text}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    
    # List Files
    st.subheader("Stored Documents")
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        list_url = f"{BACKEND_URL}/ingest/files"
        if "api/v1/api/v1" in list_url: list_url = list_url.replace("api/v1/api/v1", "api/v1")
        
        res = requests.get(list_url, headers=headers)
        if res.status_code == 200:
            files = res.json()
            if files:
                df = pd.DataFrame(files)
                st.dataframe(df, use_container_width=True)
                
                # Deletion Interface
                to_delete = st.selectbox("Select file to delete", [f['filename'] for f in files])
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if st.button("🗑️ Delete File", type="primary"):
                        del_url = f"{BACKEND_URL}/ingest/files/{to_delete}"
                        if "api/v1/api/v1" in del_url: del_url = del_url.replace("api/v1/api/v1", "api/v1")
                        requests.delete(del_url, headers=headers)
                        st.success("File deleted.")
                        time.sleep(1)
                        st.rerun()
                with col_d2:
                    if st.button("🔄 Rebuild Vector Index"):
                        reb_url = f"{BACKEND_URL}/ingest/rebuild"
                        if "api/v1/api/v1" in reb_url: reb_url = reb_url.replace("api/v1/api/v1", "api/v1")
                        with st.spinner("Rebuilding Index... This may take a while."):
                            requests.post(reb_url, headers=headers)
                            st.success("Index Rebuilt!")
            else:
                st.write("No files found in data directory.")
        else:
            st.error("Failed to fetch file list.")
    except Exception as e:
        st.error(f"Error fetching files: {e}")

# --- Main Controller ---

if not st.session_state.token:
    login_register_view()
else:
    alpha, top_k, use_exp = sidebar()
    
    if st.session_state.role == "admin":
        tab_chat, tab_kb = st.tabs(["💬 Chat", "📂 Knowledge Base"])
        with tab_chat:
            chat_interface(alpha, top_k, use_exp)
        with tab_kb:
            knowledge_base_interface()
    else:
        # Viewers only see Chat
        chat_interface(alpha, top_k, use_exp)
