import os
import json
import time
import logging
from datetime import datetime
import pytz
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# === Setup Logging ===
os.makedirs("logs", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)
log_file = f"logs/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# === Baca config.json ===
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

tz = pytz.timezone(config.get("timezone", "Asia/Jakarta"))

# === Cek Hari Libur Nasional ===
def is_libur_nasional(today):
    try:
        resp = requests.get(f"https://dayoffapi.vercel.app/api?year={today.year}&month={today.month}")
        data = resp.json()
        for item in data:
            if item.get("date") == today.strftime("%Y-%m-%d") and item.get("is_national_holiday", False):
                return True
        return False
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

# === Presensi dengan Selenium ===
def presensi(user, mode):
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])

    if not username or not password:
        logging.error(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
        return

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://dani.perhutani.co.id")

        logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
        time.sleep(2)

        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        time.sleep(3)

        # Tutup pop-up Next/Finish jika ada
        try:
            while True:
                btn_next = driver.find_element(By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Finish')]")
                btn_next.click()
                time.sleep(1)
        except:
            pass

        # Klik tombol presensi
        btn_presensi = driver.find_element(By.XPATH, "//a[contains(text(),'Klik disini untuk presensi')]")
        btn_presensi.click()
        time.sleep(2)

        screenshot_file = f"screenshots/{user['id']}_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_file)
        logging.info(f"[{user['name']}] ✅ Presensi {mode} berhasil. Screenshot: {screenshot_file}")

        driver.quit()
    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")

# === MAIN ===
now = datetime.now(tz)
today = now.date()
logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

if today.weekday() >= 5 or is_libur_nasional(today):
    logging.info("📌 Hari ini libur. Presensi dilewati.")
    exit(0)

# Mode paksa via workflow_dispatch
force_user = os.getenv("FORCE_USER", "").strip()
force_mode = os.getenv("FORCE_MODE", "").strip().lower()

for user in config["users"]:
    check_in_time = datetime.strptime(user["check_in"], "%H:%M").time()
    check_out_time = datetime.strptime(user["check_out"], "%H:%M").time()

    if force_user and force_user != user["id"]:
        continue

    if force_mode in ["checkin", "checkout"]:
        presensi(user, force_mode)
        continue

    if now.time().hour == check_in_time.hour and now.time().minute == check_in_time.minute:
        presensi(user, "checkin")
    elif now.time().hour == check_out_time.hour and now.time().minute == check_out_time.minute:
        presensi(user, "checkout")
    else:
        logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
