import os
import json
import time
import logging
import requests
import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("presensi.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Load config.json
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TIMEZONE = pytz.timezone(CONFIG.get("timezone", "Asia/Jakarta"))
TODAY = datetime.datetime.now(TIMEZONE)
TODAY_HM = TODAY.strftime("%H:%M")

# Hari ini weekend?
if TODAY.weekday() >= 5:  # 5=Sabtu, 6=Minggu
    logging.info("📌 Skip: Hari ini weekend")
    exit(0)

# Cek hari libur nasional via API (Kalender Indonesia)
def is_holiday(date: datetime.date) -> bool:
    try:
        url = f"https://dayoffapi.vercel.app/api?date={date.strftime('%Y-%m-%d')}"
        res = requests.get(url, timeout=10).json()
        return res.get("is_holiday", False)
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

if is_holiday(TODAY.date()):
    logging.info("📌 Skip: Hari ini libur nasional")
    exit(0)

def presensi(user_id, username, password, action):
    """Login & lakukan presensi"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        logging.info(f"[{user_id}] 🌐 Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )

        # Login
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(.,'Login')]").click()
        time.sleep(3)
        driver.save_screenshot(f"screenshots/{user_id}_1_login.png")

        # Tutup semua pop-up (Next/Finish)
        try:
            while True:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Next') or contains(.,'Finish')]"))
                )
                btn.click()
                time.sleep(1)
        except Exception:
            pass  # tidak ada lagi popup

        # Klik tombol utama "Klik disini untuk presensi"
        presensi_btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Klik disini untuk presensi')]"))
        )
        presensi_btn.click()
        time.sleep(3)
        driver.save_screenshot(f"screenshots/{user_id}_2_popup.png")

        # Popup terakhir: klik lagi "Klik disini untuk presensi"
        final_btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Klik disini untuk presensi')]"))
        )
        final_btn.click()
        time.sleep(3)
        driver.save_screenshot(f"screenshots/{user_id}_3_done.png")

        logging.info(f"[{user_id}] ✅ Presensi {action} berhasil!")
    except Exception as e:
        logging.error(f"[{user_id}] ❌ Error saat presensi: {e}")
        driver.save_screenshot(f"screenshots/{user_id}_error.png")
    finally:
        driver.quit()


# Jalankan untuk semua user
os.makedirs("screenshots", exist_ok=True)

logging.info(f"⏰ Sekarang {TODAY.strftime('%Y-%m-%d %H:%M')} ({CONFIG['timezone']})")

for user in CONFIG["users"]:
    uid = user["id"]
    uname = os.getenv(user["secret_user"])
    upass = os.getenv(user["secret_pass"])
    if not uname or not upass:
        logging.warning(f"[{uid}] ⚠️ Username/password tidak ditemukan di Secrets")
        continue

    # Apakah waktunya user ini check-in / check-out?
    if TODAY_HM == user["check_in"]:
        presensi(uid, uname, upass, "Check-In")
    elif TODAY_HM == user["check_out"]:
        presensi(uid, uname, upass, "Check-Out")
    else:
        logging.info(f"[{uid}] Skip (bukan jadwal user ini)")
