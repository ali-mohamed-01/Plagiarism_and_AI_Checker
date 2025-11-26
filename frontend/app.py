# frontend/app.py
import streamlit as st
import requests
import json
import pandas as pd
import io
import os

# Set BACKEND_URL to the docker service name when using docker-compose
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

st.set_page_config(page_title="RIS - Streamlit UI", layout="wide")

# Session state keys
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None

def api_headers():
    headers = {}
    if st.session_state["token"]:
        headers["Authorization"] = f"Bearer {st.session_state['token']}"
    return headers

def register_ui():
    st.header("Register")
    with st.form("reg"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["researcher", "admin"])
        name = st.text_input("Name (optional)")
        submitted = st.form_submit_button("Register")
        if submitted:
            resp = requests.post(f"{BACKEND_URL}/register", data={"email": email, "password": password, "role": role, "name": name})
            if resp.status_code in (200,201):
                st.success("Registered. Please login.")
            else:
                st.error(resp.json())

def login_ui():
    st.header("Login")
    with st.form("login"):
        username = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = requests.post(f"{BACKEND_URL}/token", data={"username": username, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["user"] = data["user"]
                st.success("Login successful")
                st.experimental_rerun()
            else:
                st.error(resp.json())

def show_profile():
    st.header("Profile")
    headers = api_headers()
    resp = requests.get(f"{BACKEND_URL}/profile", headers=headers)
    if resp.status_code == 200:
        profile = resp.json()
        st.json(profile)
        with st.form("edit_profile"):
            name = st.text_input("Name", value=profile.get("name",""))
            affiliation = st.text_input("Affiliation", value=profile.get("affiliation",""))
            fos = st.text_input("Field of study", value=profile.get("field_of_study",""))
            submitted = st.form_submit_button("Update")
            if submitted:
                r2 = requests.post(f"{BACKEND_URL}/profile/edit", data={"name": name, "affiliation": affiliation, "field_of_study": fos}, headers=headers)
                if r2.status_code == 200:
                    st.success("Profile updated")
                else:
                    st.error(r2.json())
    else:
        st.error("Could not fetch profile")

def buy_credits_ui():
    st.header("Purchase Credits")
    amount = st.number_input("Credits to purchase", min_value=1, value=5)
    if st.button("Purchase (mock)"):
        headers = api_headers()
        resp = requests.post(f"{BACKEND_URL}/purchase_credits", data={"amount": int(amount)}, headers=headers)
        if resp.status_code == 200:
            st.success(f"Purchased. New credits: {resp.json().get('credits')}")
        else:
            st.error(resp.json())

def submit_scan_ui():
    st.header("Submit Document for Integrity Scan")
    st.info("Supported: pdf, docx, txt. Max 100MB. (Virus-scan simulated)")
    uploaded_file = st.file_uploader("Choose file", type=["pdf","docx","txt","rtf"], accept_multiple_files=False)
    store_for_future = st.checkbox("Consent to store this document in closed DB for future comparisons")
    retention_days = st.number_input("Retention days", min_value=1, max_value=365, value=30)
    if st.button("Start Integrity Scan"):
        if uploaded_file is None:
            st.warning("Upload file first")
            return
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        data = {"store_for_future": store_for_future, "retention_days": retention_days}
        headers = api_headers()
        resp = requests.post(f"{BACKEND_URL}/submissions", headers=headers, data=data, files=files)
        if resp.status_code in (200,201):
            st.success(f"Submitted. File ID: {resp.json().get('file_id')}")
        else:
            st.error(resp.text)

def view_reports_ui():
    st.header("View Reports")
    headers = api_headers()
    profile = requests.get(f"{BACKEND_URL}/profile", headers=headers).json()
    subs = profile.get("submissions", [])
    if not subs:
        st.info("No submissions yet")
        return
    sel = st.selectbox("Select Submission ID", subs)
    if st.button("Load Report"):
        resp = requests.get(f"{BACKEND_URL}/submissions/{sel}/report", headers=headers)
        if resp.status_code == 200:
            report = resp.json()
            st.subheader("Summary")
            st.json(report.get("summary"))
            st.subheader("Per-sentence")
            df = pd.DataFrame(report.get("per_sentence", []))
            st.dataframe(df)
            # download pdf
            pdf_resp = requests.get(f"{BACKEND_URL}/submissions/{sel}/report/pdf", headers=headers)
            if pdf_resp.status_code == 200:
                st.download_button("Download PDF", data=pdf_resp.content, file_name=f"integrity_report_{sel}.pdf", mime="application/pdf")
        else:
            st.error(resp.text)

def logout():
    for k in ["token","user"]:
        if k in st.session_state:
            del st.session_state[k]
    st.experimental_rerun()

# Main Navigation
if st.session_state["token"] is None:
    tabs = st.tabs(["Login","Register"])
    with tabs[0]:
        login_ui()
    with tabs[1]:
        register_ui()
else:
    st.sidebar.title(f"Hello {st.session_state['user']['email']}")
    action = st.sidebar.radio("Go to", ["Profile","Submit Scan","View Reports","Buy Credits","Logout"])
    if action == "Profile":
        show_profile()
    elif action == "Submit Scan":
        submit_scan_ui()
    elif action == "View Reports":
        view_reports_ui()
    elif action == "Buy Credits":
        buy_credits_ui()
    elif action == "Logout":
        logout()
