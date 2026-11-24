# Deploy on Streamlit Community Cloud (free)

You do these steps yourself; your API key never goes into the repo.

1. Make sure the latest code is on GitHub (`main` branch of `ksrinivasarao2012/loan-servicing-agent`).
2. Go to **https://share.streamlit.io** and sign in with your GitHub account.
3. Click **Create app** (top right), then **"Yup, I have an app"**.
4. Fill in:
   - Repository: `ksrinivasarao2012/loan-servicing-agent`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: optional, e.g. `velmora-loan-agent`
5. Click **Advanced settings**:
   - **Python version:** pick **3.11** (the project needs 3.11+; the default is 3.12, which also works).
   - **Secrets:** paste this, with your real key in place of the dots:

     ```toml
     LLM_PROVIDER = "gemini"
     GEMINI_API_KEY = "..."
     GEMINI_MODEL = "gemini-3.5-flash-lite"
     ```

     To use Groq instead:

     ```toml
     LLM_PROVIDER = "groq"
     GROQ_API_KEY = "..."
     GROQ_MODEL = "llama-3.3-70b-versatile"
     ```
   - Click **Save**.
6. Click **Deploy** and wait a few minutes. Build logs appear on the right.
7. Open the app and try a message from the sidebar ("Example messages").

## Notes
- Community Cloud reads `uv.lock` first (it checks uv.lock before requirements.txt), so it installs the exact versions we tested. `requirements.txt` is kept as a plain-pip fallback.
- `app.py` copies the secrets into environment variables, so the same code works locally (`.env`) and on the cloud (Secrets).
- To change the key later: app menu (⋮) -> **Settings** -> **Secrets**, edit, save. The app restarts.
- Free-tier rate limits are shared by everyone who opens your public app. If you share the link widely, expect occasional "rate limit" errors.
