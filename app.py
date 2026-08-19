import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

st.title("AI Scribe — Prototype")
st.write("If you can see this, Streamlit is running correctly.")

api_key = os.getenv("GROQ_API_KEY")
if api_key:
    st.success("Groq API key loaded successfully.")
else:
    st.error("No API key found — check your .env file.")