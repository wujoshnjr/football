import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Hedge Fund v40 REAL DATA Alpha", layout="wide")

# =========================
# 🔑 REAL APIs
# =========================
ODDS_API_KEY = "Rd1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🗄️ REAL DATA WAREHOUSE
# =========================
conn = sqlite
