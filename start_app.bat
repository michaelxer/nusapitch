@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
)

call ".venv\Scripts\activate.bat"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app\streamlit_app.py
