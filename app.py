"""Streamlit chat UI for the Velmora Home Loans demo agent.

Run locally:  uv run streamlit run app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))  # so Streamlit Cloud finds the package

from loan_agent.graph import Agent  # noqa: E402
from loan_agent.llm import LLMError, make_llm  # noqa: E402
from loan_agent.tools import load_customers  # noqa: E402

st.set_page_config(page_title="Velmora Home Loans - demo agent", layout="wide")

# On Streamlit Community Cloud, keys live in st.secrets; copy them into env vars.
try:
    for k in ("LLM_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL", "GROQ_API_KEY", "GROQ_MODEL"):
        if k in st.secrets and not os.getenv(k):
            os.environ[k] = str(st.secrets[k])
except Exception:  # no secrets file locally: .env is used instead
    pass


def new_agent():
    st.session_state.agent = Agent(make_llm())
    st.session_state.turns = []


st.title("Velmora Home Loans - customer service agent")
st.info("Demo with fake data. Text only. Velmora Home Loans is a made-up company.")

if "agent" not in st.session_state:
    try:
        new_agent()
    except LLMError as e:
        st.error(f"Could not start the LLM: {e}")
        st.stop()

with st.sidebar:
    st.subheader("Settings")
    st.write(f"Model: `{st.session_state.agent.llm.name}`")
    if st.button("Start a new conversation"):
        new_agent()
        st.rerun()
    st.subheader("Fake customers to try")
    st.caption("Give the agent a loan ID and date of birth to verify.")
    st.table([{"Loan ID": c["loan_id"], "DOB": c["date_of_birth"], "Situation": c["profile"][4:]}
              for c in load_customers().values()])
    st.subheader("Example messages")
    st.markdown(
        "- My EMI was taken twice this month. VL1001, 1988-04-12\n"
        "- VL1003 born 22/01/1985: what's my foreclosure amount, and can I get my property papers?\n"
        "- VL1005 1982-12-03 there's a debit I never made, and I also want to know my foreclosure amount\n"
        "- Can I get a car loan?"
    )

chat, panel = st.columns([3, 2], gap="large")

prompt = st.chat_input("Type your message...")
if prompt:
    try:
        trace = st.session_state.agent.run_turn(prompt)
    except LLMError as e:
        trace = {"reply": f"(LLM error, please try again: {e})", "intents": [], "sops_used": [],
                 "tool_calls": [], "handoffs": [], "verification": None, "llm_calls": 0,
                 "retrieval": []}
    st.session_state.turns.append({"user": prompt, **trace})

with chat:
    st.subheader("Chat")
    for t in st.session_state.turns:
        with st.chat_message("user"):
            st.write(t["user"])
        with st.chat_message("assistant"):
            st.write(t["reply"])

with panel:
    st.subheader("What the agent did")
    if not st.session_state.turns:
        st.caption("Send a message to see intents, SOPs, tool calls and handoffs here.")
    for i, t in reversed(list(enumerate(st.session_state.turns, 1))):
        with st.expander(f"Turn {i}: {t['user'][:40]}", expanded=(i == len(st.session_state.turns))):
            st.markdown(f"**Detected intents:** {', '.join(t['intents']) or 'none'}")
            st.markdown(f"**Identity check:** {t['verification'] or '-'}")
            st.markdown(f"**SOPs used:** {', '.join(t['sops_used']) or 'none'}")
            for r in t.get("retrieval", []):
                st.caption(f"BM25 for '{r['query']}': top = {r['top_sop']} {r['scores']}")
            st.markdown(f"**Tool calls ({len(t['tool_calls'])}):**")
            for c in t["tool_calls"]:
                st.markdown(f"`{c['tool']}`")
                st.json({"inputs": c["inputs"], "output": c["output"]}, expanded=False)
            if t["handoffs"]:
                st.markdown("**Handoff to human:**")
                for h in t["handoffs"]:
                    st.warning(f"{h['handoff_id']} - {h['reason']}")
                    if h.get("summary"):
                        st.caption(h["summary"])
            st.caption(f"LLM calls this turn: {t['llm_calls']}")
