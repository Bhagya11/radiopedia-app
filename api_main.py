# api_main.py

import os
import uuid
import requests
import pandas as pd
from io import BytesIO
from enum import Enum
from datetime import datetime
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from requests.exceptions import RequestException, HTTPError
import time
import random

# Enums for dropdown menus
class FileFormat(str, Enum):
    json = "json"
    excel = "excel"

class ArticleSectionName(str, Enum):
    ANATOMY = "Anatomy"
    APPROACH = "Approach"
    ARTIFICIAL_INTELLIGENCE = "Artificial Intelligence"
    CLASSIFICATIONS = "Classifications"
    GAMUTS = "Gamuts"
    IMAGING_TECHNOLOGY = "Imaging Technology"
    INTERVENTIONAL_RADIOLOGY = "Interventional Radiology"
    MNEMONICS = "Mnemonics"
    PATHOLOGY = "Pathology"
    RADIOGRAPHY = "Radiography"
    SIGNS = "Signs"
    STAGING = "Staging"
    SYNDROMES = "Syndromes"

class ArticleSystemName(str, Enum):
    BREAST = "Breast"
    CARDIAC = "Cardiac"
    CENTRAL_NERVOUS_SYSTEM = "Central Nervous System"
    CHEST = "Chest"
    FORENSIC = "Forensic"
    GASTROINTESTINAL = "Gastrointestinal"
    GYNAECOLOGY = "Gynaecology"
    HAEMATOLOGY = "Haematology"
    HEAD_AND_NECK = "Head & Neck"
    HEPATOBILIARY = "Hepatobiliary"
    INTERVENTIONAL = "Interventional"
    MUSCULOSKELETAL = "Musculoskeletal"
    OBSTETRICS = "Obstetrics"
    ONCOLOGY = "Oncology"
    PAEDIATRICS = "Paediatrics"
    SPINE = "Spine"
    TRAUMA = "Trauma"
    UROGENITAL = "Urogenital"
    VASCULAR = "Vascular"

class CaseSystemName(str, Enum):
    BREAST = "Breast"
    CARDIAC = "Cardiac"
    CENTRAL_NERVOUS_SYSTEM = "Central Nervous System"
    CHEST = "Chest"
    FORENSIC = "Forensic"
    GASTROINTESTINAL = "Gastrointestinal"
    GYNAECOLOGY = "Gynaecology"
    HAEMATOLOGY = "Haematology"
    HEAD_AND_NECK = "Head & Neck"
    HEPATOBILIARY = "Hepatobiliary"
    INTERVENTIONAL = "Interventional"
    MUSCULOSKELETAL = "Musculoskeletal"
    OBSTETRICS = "Obstetrics"
    ONCOLOGY = "Oncology"
    PAEDIATRICS = "Paediatrics"
    SPINE = "Spine"
    TRAUMA = "Trauma"
    UROGENITAL = "Urogenital"
    VASCULAR = "Vascular"
    NOT_APPLICABLE = "Not Applicable"

# FastAPI app instance
app = FastAPI(
    title="Radiopaedia Scraper API",
    description="An API to scrape case and article data from radiopaedia.org. Filter using interactive dropdowns. Results can be returned as JSON, downloaded as Excel, and images saved.",
    version="2.0.0"
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

BASE_IMAGE_DIR = "downloaded_images"
os.makedirs(BASE_IMAGE_DIR, exist_ok=True)


def _scrape_articles_from_url(base_url_template: str, pages: int):
    all_pages_articles = {}
    session = requests.Session()
    for pg in range(1, pages + 1):
        articles_on_this_page = []
        url = base_url_template.format(page=pg)
        try:
            response = session.get(url, headers=HEADERS, timeout=25)
            if response.status_code == 429:
                time.sleep(10)
                response = session.get(url, headers=HEADERS, timeout=25)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for article_link in soup.find_all("a", {"class": "search-result search-result-article"}):
                article_data = {}
                article_url = "https://radiopaedia.org" + article_link.get("href")
                article_data['url'] = article_url
                try:
                    req1 = session.get(article_url, headers=HEADERS, timeout=25)
                    if req1.status_code == 429:
                        time.sleep(10)
                        req1 = session.get(article_url, headers=HEADERS, timeout=25)
                    req1.raise_for_status()
                    soup1 = BeautifulSoup(req1.content, "html.parser")
                    if title_tag := soup1.find("h1", {"class": "header-title"}):
                        article_data['title'] = title_tag.text.strip()
                    if author_info := soup1.find("div", {"class": "author-info"}):
                        article_data['date'] = author_info.text.split(" on ")[-1].strip()
                    description_text = ""
                    if body_content := soup1.find("div", {"class": "body user-generated-content"}):
                        paragraphs = body_content.find_all('p')
                        description_text = "\n".join([p.text.strip() for p in paragraphs])
                    article_data['description'] = description_text
                except (HTTPError, RequestException):
                    pass
                articles_on_this_page.append(article_data)
                time.sleep(random.uniform(1, 2))
            all_pages_articles[f'page_{pg}'] = articles_on_this_page
            time.sleep(random.uniform(2, 4))
        except (HTTPError, RequestException) as e:
            raise Exception(f"Failed on page {pg}: {e}")
    return all_pages_articles


def _scrape_cases_from_url(url_template: str, pages: int, save_images: bool = False, image_dir: str = None):
    final_data = {}
    session = requests.Session()

    for pg in range(1, pages + 1):
        temp_data = []
        url = url_template.format(page=pg)
        try:
            res = session.get(url, headers=HEADERS, timeout=25)
            if res.status_code == 429:
                time.sleep(10)
                res = session.get(url, headers=HEADERS, timeout=25)
            res.raise_for_status()
            soup = BeautifulSoup(res.content, "html.parser")
            for i in soup.find_all("a", {"class": "search-result search-result-case"}):
                local_data = {}
                patient_id = str(uuid.uuid4())
                local_data['patient_id'] = patient_id
                try:
                    case_url = "https://radiopaedia.org" + i.get("href")
                    local_data['url'] = case_url

                    res_case = session.get(case_url, headers=HEADERS, timeout=25)
                    if res_case.status_code == 429:
                        time.sleep(10)
                        res_case = session.get(case_url, headers=HEADERS, timeout=25)
                    res_case.raise_for_status()
                    soup_case = BeautifulSoup(res_case.content, "html.parser")

                    if pres := soup_case.find("div", {"id": "case-patient-presentation"}):
                        if p_tag := pres.find("p"):
                            local_data['presentation'] = p_tag.text.strip()

                    p_data_list = [d.text.strip() for d in soup_case.select("div.case-section div.data-item")]
                    local_data['patient_data'] = " ".join(p_data_list)

                    if bs := soup_case.find("div", {"class": "body sub-section"}):
                        case_parts = bs.text.strip().split("Case Discussion")
                        local_data["case_discussion"] = case_parts[-1].strip()

                    image_findings_list = [p.text.strip() for p in soup_case.select("div.study-findings p")]
                    local_data['image_findings'] = " ".join(image_findings_list)

                    if tt := i.find("h4", {"class": "search-result-title-text"}):
                        local_data['title'] = tt.text.strip()

                    if it := i.find("img", {"class": "media-object centered-image"}):
                        image_url = it.get("src")
                        local_data['image_url'] = image_url
                        if save_images and image_dir and image_url:
                            try:
                                image_filename = f"{patient_id}.jpg"
                                image_path = os.path.join(image_dir, image_filename)
                                img_req = requests.get(image_url, timeout=25, headers=HEADERS)
                                img_req.raise_for_status()
                                with open(image_path, 'wb') as f:
                                    f.write(img_req.content)
                            except (RequestException, IOError):
                                pass

                    temp_data.append(local_data)
                    time.sleep(random.uniform(1, 2))
                except Exception:
                    continue

            final_data[f"page_{pg}"] = temp_data
            time.sleep(random.uniform(2, 4))

        except Exception as e:
            raise Exception(f"Failed on page {pg}: {e}")

    return final_data


def scrape_recent_articles(pages: int):
    url_template = "https://radiopaedia.org/search?page={page}&scope=articles&sort=date_of_last_edit"
    return _scrape_articles_from_url(url_template, pages)


def scrape_articles_by_section(pages: int, section: str):
    url_template = f"https://radiopaedia.org/search?scope=articles&section={section}&page={{page}}"
    return _scrape_articles_from_url(url_template, pages)


def scrape_articles_by_system(pages: int, system: str):
    url_template = f"https://radiopaedia.org/search?scope=articles&system={system}&page={{page}}"
    return _scrape_articles_from_url(url_template, pages)


def scrape_recent_cases(pages: int, save_images: bool, image_dir: str):
    url_template = "https://radiopaedia.org/search?scope=cases&sort=date_of_publication&page={page}"
    return _scrape_cases_from_url(url_template, pages, save_images, image_dir)


def scrape_cases_by_system(pages: int, system: str, save_images: bool, image_dir: str):
    url_template = f"https://radiopaedia.org/search?scope=cases&system={system}&page={{page}}"
    return _scrape_cases_from_url(url_template, pages, save_images, image_dir)


async def _prepare_response(data: dict, file_format: FileFormat, filename_base: str, image_save_info: dict = {"saved": False, "directory": None}):
    if file_format == FileFormat.excel:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for page_key, page_data in data.items():
                if page_data:
                    df = pd.DataFrame(page_data)
                    sheet_name = f"Page {page_key.replace('page_', '')}"
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        output.seek(0)
        safe_filename_base = "".join(c if c.isalnum() else "_" for c in filename_base)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_filename_base}_{timestamp}.xlsx"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        if image_save_info["saved"]:
            headers["X-Image-Save-Path"] = image_save_info["directory"]
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers=headers
        )
    else:
        response_content = {"data": data}
        if image_save_info["saved"]:
            response_content["image_save_info"] = image_save_info
        return JSONResponse(content=response_content)


@app.get("/articles/recent", tags=["Radiopaedia Articles"])
async def get_recent_articles_endpoint(
    pages: int = Query(1, ge=1, le=5, description="Number of pages to scrape (Max 5)."),
    file_format: FileFormat = Query(FileFormat.json, description="Output format: JSON or Excel.")
):
    try:
        data = scrape_recent_articles(pages=pages)
        if not data or all(not v for v in data.values()):
            raise HTTPException(status_code=404, detail="No articles found.")
        return await _prepare_response(data, file_format, "recent_articles", {"saved": False})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/articles/by-section/{section_name}", tags=["Radiopaedia Articles"])
async def get_articles_by_section_endpoint(
    section_name: str = Path(..., example="Anatomy", description="Article section (case-sensitive)."),
    pages: int = Query(1, ge=1, le=5, description="Pages to scrape (Max 5)."),
    file_format: FileFormat = Query(FileFormat.json, description="Output format: JSON or Excel.")
):
    try:
        data = scrape_articles_by_section(pages=pages, section=section_name)
        if not data or all(not v for v in data.values()):
            raise HTTPException(status_code=404, detail=f"No articles found for section '{section_name}'.")
        filename_base = f"articles_section_{section_name.replace(' ', '_')}"
        return await _prepare_response(data, file_format, filename_base, {"saved": False})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/articles/by-system/{system_name}", tags=["Radiopaedia Articles"])
async def get_articles_by_system_endpoint(
    system_name: str = Path(..., example="Central Nervous System", description="Medical system (case-sensitive)."),
    pages: int = Query(1, ge=1, le=5, description="Pages to scrape (Max 5)."),
    file_format: FileFormat = Query(FileFormat.json, description="Output format: JSON or Excel.")
):
    try:
        data = scrape_articles_by_system(pages=pages, system=system_name)
        if not data or all(not v for v in data.values()):
            raise HTTPException(status_code=404, detail=f"No articles found for system '{system_name}'.")
        filename_base = f"articles_system_{system_name.replace(' ', '_')}"
        return await _prepare_response(data, file_format, filename_base, {"saved": False})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/cases/recent", tags=["Radiopaedia Cases"])
async def get_recent_cases_endpoint(
    pages: int = Query(1, ge=1, le=5, description="Pages to scrape (Max 5)."),
    file_format: FileFormat = Query(FileFormat.json, description="Output format: JSON or Excel."),
    save_images: bool = Query(False, description="Save case images to server?")
):
    try:
        image_dir, image_save_info = None, {"saved": False, "directory": None}
        if save_images:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_dir_name = f"recent_cases_{timestamp}"
            image_dir = os.path.join(BASE_IMAGE_DIR, unique_dir_name)
            os.makedirs(image_dir, exist_ok=True)
            image_save_info = {"saved": True, "directory": os.path.abspath(image_dir)}

        data = scrape_recent_cases(pages=pages, save_images=save_images, image_dir=image_dir)
        if not data or all(not v for v in data.values()):
            raise HTTPException(status_code=404, detail="No cases found.")
        return await _prepare_response(data, file_format, "recent_cases", image_save_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/cases/by-system/{system_name}", tags=["Radiopaedia Cases"])
async def get_cases_by_system_endpoint(
    system_name: str = Path(..., example="Chest", description="Medical system (case-sensitive)."),
    pages: int = Query(1, ge=1, le=5, description="Pages to scrape (Max 5)."),
    file_format: FileFormat = Query(FileFormat.json, description="Output format: JSON or Excel."),
    save_images: bool = Query(False, description="Save case images to server?")
):
    try:
        image_dir, image_save_info = None, {"saved": False, "directory": None}
        if save_images:
            safe_system_name = "".join(c if c.isalnum() else "_" for c in system_name)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_dir_name = f"cases_{safe_system_name}_{timestamp}"
            image_dir = os.path.join(BASE_IMAGE_DIR, unique_dir_name)
            os.makedirs(image_dir, exist_ok=True)
            image_save_info = {"saved": True, "directory": os.path.abspath(image_dir)}

        data = scrape_cases_by_system(pages=pages, system=system_name, save_images=save_images, image_dir=image_dir)
        if not data or all(not v for v in data.values()):
            raise HTTPException(status_code=404, detail=f"No cases found for system '{system_name}'.")
        filename_base = f"cases_system_{system_name.replace(' ', '_')}"
        return await _prepare_response(data, file_format, filename_base, image_save_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
