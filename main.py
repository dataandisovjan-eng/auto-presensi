import os
import json
import time
import logging
import requests
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

CONFIG_FILE = "config.json"
LOGIN_URL = "https://dani.perhutani.co.id"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def is_holiday(today):
    """Cek API Hari Libur Nasional"""
    try:
        resp = requests.get("https://api-harilibur.vercel.app/api", timeout=10)
        data = resp.json()
        if isinstance(data, list):
            for d in data:
                if d.get("is_national_holiday") and d.get("holiday_date") == today.strftime("%Y-%m-%d"):
                    return True
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
    return False

def do_presensi(user, action):
    """Login dan klik tombol presensi"""
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])

    if not username or not password:
        logging.error(f"[{user['id']}] ⚠️ Username/password tidak ditemukan di Secrets")
        return False

    logging.info(f"[{user['id']}] Mulai presensi {action}...")

    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        wait = WebDriverWait(driver, 20)
        driver.get(LOGIN_URL)

        # Login
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]"))).click()

        # Handle popup Next → Finish (jika ada)
        time.sleep(2)
        while True:
            try:
                next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]")))
                next_btn.click()
                time.sleep(1)
            except:
                try:
                    finish_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Finish')]")
                    finish_btn.click()
                    time.sleep(1)
                except:
                    break

        # Klik tombol presensi utama
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))).click()
        time.sleep(2)

        # Popup terakhir presensi
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))).click()
        time.sleep(2)

        # Screenshot bukti
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/{user['id']}_{action}_{int(time.time())}.png"
        driver.save_screenshot(filename)
        logging.info(f"[{user['id']}] Presensi {action} selesai ✅ (screenshot disimpan: {filename})")

        driver.quit()
        return True

    except Exception as e:
        logging.error(f"[{user['id']}] ❌ Error saat presensi: {e}")
        return False

def main():
    config = load_config()
    tz = pytz.timezone(config.get("timezone", "Asia/Jakarta"))
    now = datetime.now(tz)
    today = now.date()
    jam_sekarang = now.strftime("%H:%M")
    hari = now.strftime("%A")

    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

    # Skip sabtu/minggu/libur
    if hari in ["Saturday", "Sunday"] or is_holiday(today):
        logging.info("📌 Hari ini libur, tidak ada presensi.")
        return

    # Mode debug (paksa jalan)
    force_user = os.getenv("FORCE_USER")
    force_action = os.getenv("FORCE_ACTION")

    for user in config["users"]:
        # Jika pakai mode debug
        if force_user and force_action:
            if user["id"] == force_user:
                logging.info(f"[DEBUG] 🚀 Jalankan paksa {force_action} untuk {user['name']}")
                do_presensi(user, force_action)
            continue

        # Normal mode
        if jam_sekarang == user["check_in"]:
            do_presensi(user, "check_in")
        elif jam_sekarang == user["check_out"]:
            do_presensi(user, "check_out")
        else:
            logging.info(f"[{user['id']}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
