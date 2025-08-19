# streamlit_app.py

import streamlit as st
import requests
import pandas as pd
from io import BytesIO
import threading
import uvicorn

# --- Additions for Combined Deployment ---
# Import your FastAPI app object from your api_main.py file
from api_main import app as fastapi_app

# Define the function to run the Uvicorn server
# It must be run on 0.0.0.0 to be accessible within the container
def run_fastapi():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

# Use a daemon thread to run the API in the background
# This thread will automatically stop when the Streamlit app stops
daemon_thread = threading.Thread(target=run_fastapi, daemon=True)
# Start the thread only if it's not already running
if not daemon_thread.is_alive():
    daemon_thread.start()
# --- End of Additions ---


st.set_page_config(page_title="Radiopaedia Scraper", layout="wide")
st.title("Radiopaedia Scraper Data Viewer")
st.markdown("A simple UI to fetch data from the Radiopaedia Scraper API.")

# Sidebar - Endpoint selection and parameters
st.sidebar.title("Scraper Controls")
endpoint = st.sidebar.selectbox(
    "Choose endpoint",
    [
        "Recent Articles",
        "Articles by Section",
        "Articles by System",
        "Recent Cases",
        "Cases by System"
    ]
)

# The API limits pages to 5, so the frontend should reflect this.
pages = st.sidebar.number_input("Pages to fetch", min_value=1, max_value=5, value=1, step=1)
file_format = st.sidebar.selectbox("Output Format", ["json", "excel"])

section_name = ""
system_name = ""
save_images = False

if endpoint == "Articles by Section":
    section_name = st.sidebar.selectbox(
        "Article Section",
        [
            "Anatomy", "Approach", "Artificial Intelligence", "Classifications",
            "Gamuts", "Imaging Technology", "Interventional Radiology",
            "Mnemonics", "Pathology", "Radiography", "Signs", "Staging", "Syndromes"
        ]
    )
elif endpoint in ["Articles by System", "Cases by System"]:
    system_name = st.sidebar.selectbox(
        "Medical System",
        [
            "Breast", "Cardiac", "Central Nervous System", "Chest", "Forensic",
            "Gastrointestinal", "Gynaecology", "Haematology", "Head & Neck", "Hepatobiliary",
            "Interventional", "Musculoskeletal", "Obstetrics", "Oncology", "Paediatrics",
            "Spine", "Trauma", "Urogenital", "Vascular", "Not Applicable"
        ]
    )

if endpoint in ["Recent Cases", "Cases by System"]:
    # Inform user that saving images is not practical on Streamlit Cloud
    st.sidebar.warning("Image saving occurs on the server's temporary file system and cannot be accessed directly from the cloud.")
    save_images = st.sidebar.checkbox("Save images on server? (Temporary)")


# --- CRUCIAL CHANGE: Point to the locally running API ---
BASE_URL = "http://localhost:8000"

def build_api_url():
    """Constructs the full API URL based on sidebar selections."""
    # Sanitize URL parts
    safe_section = requests.utils.quote(section_name)
    safe_system = requests.utils.quote(system_name)
    
    if endpoint == "Recent Articles":
        return f"{BASE_URL}/articles/recent?pages={pages}&file_format={file_format}"
    elif endpoint == "Articles by Section":
        return f"{BASE_URL}/articles/by-section/{safe_section}?pages={pages}&file_format={file_format}"
    elif endpoint == "Articles by System":
        return f"{BASE_URL}/articles/by-system/{safe_system}?pages={pages}&file_format={file_format}"
    elif endpoint == "Recent Cases":
        return f"{BASE_URL}/cases/recent?pages={pages}&file_format={file_format}&save_images={str(save_images).lower()}"
    elif endpoint == "Cases by System":
        return f"{BASE_URL}/cases/by-system/{safe_system}?pages={pages}&file_format={file_format}&save_images={str(save_images).lower()}"
    return None

if st.sidebar.button("Fetch Data"):
    api_url = build_api_url()
    st.info(f"Requesting data from local API endpoint...")
    st.write(f"`GET {api_url}`")

    try:
        # Show a spinner while the scraping happens
        with st.spinner('Scraping data from Radiopaedia... This may take a moment.'):
            # Increase the timeout because scraping can be slow
            response = requests.get(api_url, timeout=300)

        if response.status_code != 200:
            st.error(f"API Error: Status code {response.status_code}")
            st.json(response.json())
        else:
            st.success("Data fetched successfully!")
            if file_format == "json":
                data = response.json()
                for page_key, page_data in data.get("data", {}).items():
                    st.subheader(page_key.replace("_", " ").title())
                    if not page_data:
                        st.write("No data found for this page.")
                    else:
                        df = pd.DataFrame(page_data)
                        st.dataframe(df)
                if "image_save_info" in data and data["image_save_info"]["saved"]:
                    st.success(f"Images were saved on the server at: {data['image_save_info']['directory']}")
            
            else: # Excel format
                st.subheader("Excel File Content")
                # Provide a download button for the Excel file
                st.download_button(
                   label="Download Excel file",
                   data=response.content,
                   file_name="radiopaedia_data.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Optionally display the content of the Excel file
                with BytesIO(response.content) as b:
                    xls = pd.ExcelFile(b)
                    for sheet in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet)
                        st.write(f"Sheet: {sheet}")
                        st.dataframe(df)

                if "X-Image-Save-Path" in response.headers:
                    st.success(f"Images were saved on the server at: {response.headers['X-Image-Save-Path']}")

    except requests.exceptions.RequestException as e:
        st.error(f"A network request exception occurred: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
