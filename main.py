import os
import time
import logging
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== Setup Logging =====
log_file = f"log_presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_print(msg):
    print(msg)
    logging.info(msg)

# ===== Konfigurasi dari Secrets GitHub =====
USERNAME = os.getenv("PRESENSI_USERNAME")
PASSWORD = os.getenv("PRESENSI_PASSWORD")
SITE_URL = "https://dani.perhutani.co.id"

# ===== Cek Hari Libur & Weekend =====
def is_holiday():
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().weekday()  # 0=Senin, 6=Minggu
    if weekday >= 5:
        log_print("🚫 Hari ini Sabtu/Minggu. Skip presensi.")
        return True
    try:
        resp = requests.get("https://dayoffapi.vercel.app/api", timeout=10)
        holidays = resp.json().get("holidays", [])
        if today in holidays:
            log_print("🚫 Hari libur nasional. Skip presensi.")
            return True
    except Exception as e:
        log_print(f"⚠️ Gagal cek API Hari Libur: {e}")
    return False

# ===== Proses Presensi =====
def presensi():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        log_print("🌐 Membuka halaman login...")
        driver.get(SITE_URL)

        # Login
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
        log_print("✅ Login berhasil")

        # Klik semua popup "Next" sampai habis
        while True:
            try:
                next_btn = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Finish')]"))
                )
                btn_text = next_btn.text
                next_btn.click()
                log_print(f"➡️ Klik tombol popup: {btn_text}")
                time.sleep(1)
                if "Finish" in btn_text:
                    break
            except:
                break

        # Klik tombol presensi utama
        presensi_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))
        )
        presensi_btn.click()
        log_print("🟠 Klik tombol presensi utama")

        # Klik tombol presensi dalam popup terakhir
        popup_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))
        )
        popup_btn.click()
        log_print("✅ Presensi berhasil")

        # Simpan screenshot
        screenshot_file = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_file)
        log_print(f"📸 Screenshot disimpan: {screenshot_file}")

        # Simpan HTML terakhir
        html_file = f"page_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log_print(f"📝 HTML source disimpan: {html_file}")

    except Exception as e:
        log_print(f"❌ Error saat presensi: {e}")
    finally:
        driver.quit()

# ===== Main =====
if __name__ == "__main__":
    if not is_holiday():
        presensi()
    else:
        log_print("Presensi dilewati karena hari libur/weekend.")
