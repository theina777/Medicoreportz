import streamlit as st
import tempfile
import os
import copy
from Medicoreportz import analyze_file, generate_summary

st.set_page_config(
    page_title="MedicoReportz",
    page_icon="🧬",
    layout="wide"
)

st.markdown("""
<style>
:root {
    --bg: #0b1220;
    --panel: #111827;
    --panel-soft: rgba(255,255,255,0.05);
    --text: #e5e7eb;
    --muted: #9ca3af;
    --accent: #3f9ca8;
    --accent-soft: rgba(63,156,168,0.18);
    --warning-bg: #3b1f24;
}

html, body, [class*="css"] {
    font-size: 18.5px !important;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

section.main > div {
    max-width: 1200px;
    margin: auto;
    padding: 48px 40px;
}

h1 {
    font-size: 2.8rem;
    font-weight: 700;
    color: var(--accent);
}

.subtitle {
    font-size: 1.15rem;
    color: var(--muted);
    max-width: 720px;
    margin-bottom: 36px;
}

.section-title {
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--accent);
    margin-top: 56px;
    margin-bottom: 22px;
}

.divider {
    border-top: 1px solid rgba(255,255,255,0.12);
    margin: 36px 0;
}

.info-row {
    display: flex;
    gap: 80px;
    font-size: 1.05rem;
    line-height: 1.8;
}

.lab {
    display: flex;
    gap: 18px;
    padding: 22px 26px;
    border-radius: 18px;
    margin-bottom: 20px;
    animation: fadeUp 0.45s ease both;
    background: var(--accent-soft);
}

.lab-warning {
    background: var(--warning-bg);
    border-left: 6px solid var(--accent);
}

.lab-icon {
    font-size: 1.4rem;
}

.summary {
    font-size: 1.05rem;
    line-height: 1.9;
    max-width: 900px;
    animation: fadeUp 0.5s ease both;
}

.data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
}

.data-block {
    background: var(--panel-soft);
    padding: 22px 24px;
    border-radius: 16px;
}

.data-block h4 {
    color: var(--accent);
    margin-bottom: 14px;
    font-size: 1.1rem;
}

@keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🧬 MedicoReportz</h1>", unsafe_allow_html=True)
st.markdown(
    "<div class='subtitle'>AI-assisted medical report explanation with clear, verifiable lab highlights.</div>",
    unsafe_allow_html=True
)

uploaded_file = st.file_uploader(
    "Upload a medical report (PDF, image, or text)",
    type=["pdf", "png", "jpg", "jpeg", "txt", "docx"]
)

if uploaded_file:
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    with st.spinner("Analyzing report…"):
        data, summary = analyze_file(tmp_path)

    if "editable_data" not in st.session_state:
        st.session_state.editable_data = copy.deepcopy(data)
        st.session_state.summary = summary

    editable = st.session_state.editable_data

    st.markdown("<div class='section-title'>👤 Patient Information</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        editable["patient"]["name"] = st.text_input("Name", editable["patient"].get("name", ""))
    with c2:
        editable["patient"]["age"] = st.text_input("Age", editable["patient"].get("age", ""))
    with c3:
        editable["patient"]["gender"] = st.text_input("Gender", editable["patient"].get("gender", ""))

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>❤️ Vital Signs</div>", unsafe_allow_html=True)
    for k in list(editable["vital_signs"].keys()):
        editable["vital_signs"][k] = st.text_input(
            k.replace("_", " ").title(),
            editable["vital_signs"][k],
            key=f"vital_{k}"
        )

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>🧪 Laboratory Results</div>", unsafe_allow_html=True)
    for i, lab in enumerate(editable["labs"]):
        cols = st.columns([3, 2, 2, 3])
        lab["test_name"] = cols[0].text_input("Test", lab["test_name"], key=f"t{i}")
        lab["value"] = cols[1].text_input("Value", lab["value"], key=f"v{i}")
        lab["unit"] = cols[2].text_input("Unit", lab["unit"], key=f"u{i}")
        lab["normal_range"] = cols[3].text_input("Normal Range", lab["normal_range"], key=f"n{i}")

        st.markdown(
            f"""
            <div class="lab {'lab-warning' if lab['highlight']=='warning' else ''}">
                <span class="lab-icon">{'⚠️' if lab['highlight']=='warning' else '✅'}</span>
                <span><b>{lab['test_name']}</b> — {lab['value']} {lab['unit']} ({lab['normal_range']})</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    if st.button("🔄 Re-generate Summary from Edited Data"):
        with st.spinner("Generating updated summary…"):
            st.session_state.summary = generate_summary(editable)

    st.markdown("<div class='section-title'>📝 Patient Summary</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='summary'>{st.session_state.summary}</div>", unsafe_allow_html=True)

    with st.expander("📄 View Technical Extracted Data"):
        st.json(editable)
