# 🔬 Research Integrity Scanner — Plagiarism & AI-Text Detection System

This project is a complete **FastAPI + Streamlit** application that performs:
- User authentication & roles  
- Document upload & secure handling  
- Plagiarism detection (mock engine)  
- AI-generated-text detection  
- Interactive color-coded similarity viewer  
- Combined PDF Integrity Report  

Designed as a full MVP covering **FR-1 → FR-11**.

---

## 🚀 Core Features (FR-1 → FR-11)

### 🔐 **User Management**
✔️ User Registration & Login (JWT Authentication)  
✔️ Role-based Access Control (Researcher / Admin)  
✔️ Profile Management (name, affiliation, field)  
✔️ Submission History Tracking  

---

### 💳 **Credits & Subscription System**  
✔️ Monthly plans *(mock)*  
✔️ Credit-based scanning  
✔️ Admin dashboard for institutional accounts *(future-ready)*  

---

### 📄 **Document Upload & Processing**
✔️ Upload PDF • DOCX • TXT • RTF  
✔️ Secure file handling  
✔️ Virus-scan placeholder  
✔️ Text extraction (mock implementation)  

---

### 🔍 **Plagiarism Detection (FR-5)**  
✔️ Fuzzy matching (n-grams / embeddings placeholder)  
✔️ Web & database similarity checks *(mock)*  
✔️ Citation & bibliography exclusion  
✔️ Quotation exclusion support  

---

### 🤖 **AI-Generated Text Detection (FR-6)**  
✔️ Per-sentence AI probability  
✔️ Burstiness & perplexity metrics  
✔️ Model-likelihood estimation (e.g., GPT-3.5 style)  
✔️ Purple-highlighted AI sentences in the viewer  

---

## 📊 Reporting & Visualization (FR-7 → FR-9)

### 🔥 **Interactive Document Viewer**
📌 Red/Orange → High similarity  
📌 Blue → Properly cited  
📌 Green → Original text  
📌 Purple → Suspected AI-generated  

### 📝 **Combined Integrity PDF Report**
- Similarity Score  
- AI Probability Score  
- Highlighted findings  
- Sources  
- Final Integrity Score  

---

## 📁 Project Structure

