import streamlit as st
from dotenv import load_dotenv
from groq import Groq
import os
import re
from datetime import datetime

load_dotenv()
st.set_page_config(page_title="AI Scribe", page_icon="🩺", layout="wide")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SAMPLE_TRANSCRIPT = """Doctor: What brings you in today?
Patient: I've had a sore throat and a fever for about three days now. It hurts to swallow.
Doctor: Any cough or runny nose?
Patient: A little bit of a dry cough, no runny nose.
Doctor: Let me take a look. Your throat looks red and I can see some white patches on your tonsils. Your temperature right now is 101.2. Lymph nodes in your neck are a bit swollen.
Doctor: This looks like it could be strep throat. I'm going to do a rapid strep test.
Patient: Okay.
Doctor: The test came back positive for strep. I'm going to prescribe amoxicillin, 500mg twice a day for 10 days. Make sure you finish the full course even if you start feeling better. Drink plenty of fluids and rest. If you're not feeling better in 3 days or it gets worse, come back in.
Patient: Should I be worried about anyone else in my house getting it?
Doctor: It's contagious, so try to avoid sharing utensils or cups until you've been on antibiotics for at least 24 hours."""

SYSTEM_PROMPT = """You are a clinical documentation assistant that drafts SOAP notes from clinical encounter transcripts, for a physician who will review and correct everything before it becomes part of the medical record. Faithfulness to the transcript matters more than polish.

CORE RULES:
1. Use ONLY information explicitly stated in the transcript. Never infer, assume, or add clinical details that were not said.
2. Keep Subjective and Objective strictly separate:
   - SUBJECTIVE = what the patient or caregiver reported, in their own terms (symptoms, history, concerns).
   - OBJECTIVE = what the clinician observed, measured, or tested (vitals, exam findings, test results). Never restate a patient-reported symptom as if it were an objective finding.
3. In ASSESSMENT, synthesize — do not just repeat the transcript. State the diagnosis/impression and its certainty:
   - If confirmed by a test or clearly stated as confirmed, say so.
   - If it's a working/clinical impression without confirmation, label it as such.
   - Never invent a diagnosis not stated or clearly implied.
4. In PLAN, be specific and tied to a problem. For every medication, include dose, route, frequency, and duration if stated. For every instruction, state what happens, for which problem, and any follow-up timing or return precautions.
5. If a section has no relevant information, write "Not discussed" — never fabricate content to fill it.
6. Do not include greetings or administrative chit-chat with no clinical relevance.

OUTPUT FORMAT — follow exactly, with these exact headers and nothing else before or after:

SUBJECTIVE:
[content]

OBJECTIVE:
[content]

ASSESSMENT:
[content]

PLAN:
[content]

MISSING OR UNCERTAIN:
[Bullet list of clinically important information NOT documented in this transcript but often needed — e.g. allergies, exact medication dose, vital signs, follow-up timing. If nothing important is missing, write "None identified."]
"""


def parse_soap_response(text):
    headers = ["SUBJECTIVE", "OBJECTIVE", "ASSESSMENT", "PLAN", "MISSING OR UNCERTAIN"]
    pattern = r"(SUBJECTIVE:|OBJECTIVE:|ASSESSMENT:|PLAN:|MISSING OR UNCERTAIN:)"
    parts = re.split(pattern, text)
    if len(parts) < 2:
        return None
    sections = {}
    it = iter(parts[1:])
    for header, content in zip(it, it):
        sections[header.replace(":", "").strip()] = content.strip()
    if not all(h in sections for h in headers):
        return None
    return sections


st.title("🩺 AI Scribe")
st.caption("Draft SOAP notes from a clinical encounter transcript. All output must be reviewed before use — this is a research prototype, not for real patient data.")

meta1, meta2 = st.columns(2)
with meta1:
    st.date_input("Encounter Date")
with meta2:
    st.text_input("Encounter / Session ID (optional)", placeholder="e.g. demo-001")

st.divider()

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.subheader("Transcript")
    if "transcript" not in st.session_state:
        st.session_state.transcript = ""
    if st.button("Load sample transcript"):
        st.session_state.transcript = SAMPLE_TRANSCRIPT
    transcript = st.text_area("Clinical Encounter Transcript", height=350, key="transcript")
    generate = st.button("Generate SOAP Note", type="primary", use_container_width=True)
    st.caption(f"Transcript length: {len(transcript)} characters — starts with: \"{transcript[:60]}...\"")

with right:
    st.subheader("Draft Note")

    if generate:
        if not transcript.strip():
            st.warning("Please enter or load a transcript first.")
        else:
            with st.spinner("Generating SOAP note..."):
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": transcript}
                        ],
                        temperature=0.2
                    )
                    raw_note = response.choices[0].message.content
                    st.session_state.raw_note = raw_note
                    st.session_state.sections = parse_soap_response(raw_note)
                    st.session_state.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.session_state.note_version = st.session_state.get("note_version", 0) + 1
                except Exception as e:
                    st.error("Something went wrong generating the note. This is often a temporary issue (e.g. rate limit) — try again in a moment.")
                    st.session_state.sections = None
                    with st.expander("Technical details"):
                        st.code(str(e))

    sections = st.session_state.get("sections")

    if sections:
        version = st.session_state.get("note_version", 0)
        for header in ["SUBJECTIVE", "OBJECTIVE", "ASSESSMENT", "PLAN"]:
            st.markdown(f"**{header.title()}**")
            st.text_area(
                label=header, value=sections[header], height=120,
                key=f"edit_{header}_{version}", label_visibility="collapsed"
    )
        missing = sections.get("MISSING OR UNCERTAIN", "")
        if missing and missing.strip().lower() not in ("none identified.", "none identified"):
            st.warning(f"**Missing or uncertain information:**\n\n{missing}")
        else:
            st.success("No obviously missing high-value fields flagged.")
        st.caption(f"Generated {st.session_state.get('generated_at', '')} · Model: openai/gpt-oss-120b · Not saved — session only")

    elif st.session_state.get("raw_note"):
        st.warning("The model's output didn't match the expected format. Showing raw output — please review carefully before relying on it.")
        st.text_area("Raw output", value=st.session_state.raw_note, height=400)