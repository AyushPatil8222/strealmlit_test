import streamlit as st
import time
from groq_trial2 import ask_hr_bot

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="KompassHR AI",
    page_icon="🤖",
    layout="centered"
)

# ----------------------------
# HEADER
# ----------------------------
st.title("🤖 KompassHR AI Assistant")
st.caption("Ask HR questions in natural language")

# ----------------------------
# SESSION STATE
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------------
# DISPLAY CHAT HISTORY
# ----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------
# USER INPUT
# ----------------------------
user_input = st.chat_input("Ask an HR question...")

if user_input:
    # Show user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    # Assistant response
    with st.chat_message("assistant"):
        placeholder = st.empty()

        with st.spinner("Thinking..."):
            try:
                result = ask_hr_bot(user_input)
                answer = result["answer"]  # ❌ no raw_data, no SQL shown
            except Exception as e:
                answer = f"❌ Error: {str(e)}"

        # Typing effect (ChatGPT style)
        full_text = ""
        for word in answer.split():
            full_text += word + " "
            time.sleep(0.02)
            placeholder.markdown(full_text)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })
