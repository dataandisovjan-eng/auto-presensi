import os
import time
import json
import logging
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === LOAD CONFIG ===
with open("config.json", "r") as f:
    CONFIG = json.load(f)

TIMEZONE = pytz.timezone(CONFIG.get("timezone", "Asia/Jakarta"))
USERS = CONFIG.get("users", [])

# === SETUP LOGGING ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def save_screenshot(driver, step_name, user):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/{user}_{step_name}_{timestamp}.png"
    driver.save_screenshot(filename)
    logging.info(f"[{user}] Screenshot saved: {filename}")

def save_html(driver, step_name, user):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/{user}_{step_name}_{timestamp}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logging.info(f"[{user}] HTML saved: {filename}")

def presensi(user):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)

        logging.info(f"[{user['name']}] Buka halaman login")
        driver.get("https://dani.perhutani.co.id")
        save_screenshot(driver, "halaman_login", user['name'])
        save_html(driver, "halaman_login", user['name'])

        # --- Login ---
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(user["username"])
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(user["password"])
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))).click()

        logging.info(f"[{user['name']}] Login berhasil")
        time.sleep(3)
        save_screenshot(driver, "setelah_login", user['name'])

        # --- Handle pop-up Next ---
        while True:
            try:
                next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]")))
                next_btn.click()
                logging.info(f"[{user['name']}] Klik Next popup")
                save_screenshot(driver, "popup_next", user['name'])
                time.sleep(1)
            except:
                break

        # --- Handle pop-up Finish ---
        try:
            finish_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Finish')]")))
            finish_btn.click()
            logging.info(f"[{user['name']}] Klik Finish popup")
            save_screenshot(driver, "popup_finish", user['name'])
            time.sleep(2)
        except:
            logging.info(f"[{user['name']}] Tidak ada popup Finish")

        # --- Klik tombol presensi utama ---
        presensi_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik Disini untuk Presensi')]")))
        presensi_btn.click()
        logging.info(f"[{user['name']}] Klik tombol presensi utama")
        save_screenshot(driver, "klik_presensi_utama", user['name'])

        # --- Popup konfirmasi presensi ---
        confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik Disini untuk Presensi')]")))
        confirm_btn.click()
        logging.info(f"[{user['name']}] Klik tombol presensi di popup")
        save_screenshot(driver, "popup_konfirmasi_presensi", user['name'])

        logging.info(f"[{user['name']}] ✅ Presensi selesai")

    except Exception as e:
        logging.error(f"[{user['name']}] Gagal presensi: {e}")
        save_screenshot(driver, "error", user['name'])
        save_html(driver, "error_page", user['name'])
    finally:
        driver.quit()

if __name__ == "__main__":
    now = datetime.now(TIMEZONE).strftime("%H:%M")
    logging.info(f"⏰ Sekarang {now}, cek jadwal user...")

    for user in USERS:
        if now == user.get("check_in") or now == user.get("check_out"):
            logging.info(f"[{user['name']}] Waktunya presensi ({now}), jalankan...")
            presensi(user)
        else:
            logging.info(f"[{user['name']}] Bukan waktunya presensi ({now}), skip...")
