import os
import time
import json
from urllib.parse import urlparse
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

from PIL import Image


# CONFIGURATION
output_folder = 'C:/Users/bruno/Documents/Annotation tool/images'
os.makedirs(output_folder, exist_ok=True)

# === Read the CSV file ===
csv_path = 'C:/Users/bruno/Documents/Annotation tool/websites/public_websites_for_dataset.csv'
df = pd.read_csv(csv_path)

screenshot_folder = os.path.join(output_folder, 'screenshots')
metadata_folder = os.path.join(output_folder, 'metadata')

os.makedirs(screenshot_folder, exist_ok=True)
os.makedirs(metadata_folder, exist_ok=True)

# SETUP CHROME DRIVER
chrome_options = Options()
chrome_options.headless = True
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--hide-scrollbars")

driver = webdriver.Chrome(options=chrome_options)

def capture_full_page_screenshots(driver, viewport_width, viewport_height, scroll_height, output_folder, filename_base):
    images = []
    current_scroll = 0
    part_number = 0

    while current_scroll < scroll_height:
        driver.execute_script(f"window.scrollTo(0, {current_scroll});")
        time.sleep(0.5)  # small pause to allow rendering

        screenshot_part_path = os.path.join(output_folder, f"{filename_base}_part{part_number}.png")
        driver.save_screenshot(screenshot_part_path)
        images.append(screenshot_part_path)

        current_scroll += viewport_height
        part_number += 1

    return images

def stitch_images_vertically(image_paths, output_path):
    images = [Image.open(p) for p in image_paths]

    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)

    stitched_image = Image.new('RGB', (max_width, total_height))

    y_offset = 0
    for img in images:
        stitched_image.paste(img, (0, y_offset))
        y_offset += img.height

    stitched_image.save(output_path)

def sanitize_filename(url):
    parsed = urlparse(url)
    filename = parsed.netloc.replace('.', '_')
    return filename

def get_doctype(driver):
    return driver.execute_script("""
        try {
            return document.doctype ? document.doctype.name : '';
        } catch (e) {
            return '';
        }
    """)

def scroll_to_bottom(driver, pause_time=1.0, max_attempts=30):
    """
    Scrolls to the bottom of the page step-by-step to trigger lazy-loading.
    
    Args:
        driver: Selenium WebDriver instance
        pause_time: Time to wait between scrolls (seconds)
        max_attempts: Max number of scroll attempts to avoid infinite loops
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    
    while attempts < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            # No more content loaded
            break
        
        last_height = new_height
        attempts += 1
    
    print(f'Finished scrolling after {attempts} attempts.')


# MAIN LOOP
for index, row in df.iterrows():
    url = row['Website URL']
    category = row['Category']
    
    print(f'[{index+1}/{len(df)}] Processing {url} ...')

    try:

        driver.get(url)

        # Wait for full load
        time.sleep(5)  # simple but effective (you can also use WebDriverWait with JS triggers)
        scroll_to_bottom(driver, pause_time=1.0, max_attempts=30)

        # Get page source and parse
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Metadata extraction
        num_dom_elements = len(soup.find_all())
        num_images = len(soup.find_all('img'))
        num_links = len(soup.find_all('a'))
        num_forms = len(soup.find_all('form'))
        num_buttons = len(soup.find_all('button'))
        language = driver.execute_script("return document.documentElement.lang || 'unknown';")
        scroll_height = driver.execute_script("return document.body.scrollHeight;")
        viewport_width = driver.execute_script("return window.innerWidth;")
        viewport_height = driver.execute_script("return window.innerHeight;")
        framework_guess = 'Unknown'

        # Simple heuristic for framework detection
        if driver.execute_script("return !!window.React || !!document.querySelector('[data-reactroot], [data-reactid]');"):
            framework_guess = 'React'
        elif driver.execute_script("return typeof Vue !== 'undefined'"):
            framework_guess = 'Vue.js'
        elif driver.execute_script("return typeof angular !== 'undefined' || !!document.querySelector('[ng-app]');"):
            framework_guess = 'Angular'

        # Screenshot
        filename_base = sanitize_filename(url)
        screenshot_path = os.path.join(screenshot_folder, f"{filename_base}.png")
        # Full-page capture in parts:
        screenshot_parts = capture_full_page_screenshots(
            driver, viewport_width, viewport_height, scroll_height, screenshot_folder, filename_base
        )

        # Stitch parts into one image:
        stitched_output_path = os.path.join(screenshot_folder, f"{filename_base}_full.png")
        stitch_images_vertically(screenshot_parts, stitched_output_path)

        print(f"Full-page screenshot saved to {stitched_output_path}")

        for p in screenshot_parts:
            os.remove(p)

        # Metadata save
        metadata = {
            'url': url,
            'title': driver.title,
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'screenshot_file': os.path.basename(screenshot_path),
            'num_dom_elements': num_dom_elements,
            'num_images': num_images,
            'num_links': num_links,
            'num_forms': num_forms,
            'num_buttons': num_buttons,
            'doctype': get_doctype(driver),
            'framework': framework_guess,
            'language': language,
            'viewport_size': f'{viewport_width}x{viewport_height}',
            'full_page_size': f'{viewport_width}x{scroll_height}',
            'scroll_height': scroll_height
        }

        metadata_path = os.path.join(metadata_folder, f"{filename_base}.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Saved screenshot and metadata for {url}\n")
    
    except Exception as e:
        print(f'❌ Failed to process {url}: {e}')

driver.quit()
print("DONE.")
