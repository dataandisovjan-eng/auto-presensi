import os
import json
import time
import logging
import pytz
import requests
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# === Logging setup ===
os.makedirs("logs", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/presensi.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# === Load config ===
with open("config.json", "r") as f:
    CONFIG = json.load(f)

TIMEZONE = pytz.timezone(CONFIG.get("timezone", "Asia/Jakarta"))
TIME_MARGIN = CONFIG.get("time_margin", 5)
TODAY = datetime.datetime.now(TIMEZONE)
TODAY_HM = TODAY.strftime("%H:%M")

logging.info(f"⏰ Sekarang {TODAY.strftime('%Y-%m-%d %H:%M')} ({CONFIG['timezone']})")

# === Cek Hari Libur Nasional ===
def is_holiday(date: datetime.date) -> bool:
    try:
        url = f"https://dayoffapi.vercel.app/api?date={date.strftime('%Y-%m-%d')}"
        res = requests.get(url, timeout=10).json()

        if isinstance(res, list):
            return any(item.get("is_holiday", False) for item in res if isinstance(item, dict))
        elif isinstance(res, dict):
            return res.get("is_holiday", False)
        return False
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

if TODAY.weekday() >= 5:  # Sabtu/Minggu
    logging.info("📌 Hari ini libur (Sabtu/Minggu), presensi dilewati.")
    exit()

if is_holiday(TODAY.date()):
    logging.info("📌 Hari ini libur nasional, presensi dilewati.")
    exit()

# === Fungsi range waktu fleksibel ===
def within_schedule(now: datetime.datetime, target_str: str, margin_min: int = 5) -> bool:
    target = datetime.datetime.combine(now.date(), datetime.datetime.strptime(target_str, "%H:%M").time())
    delta = abs((now - target).total_seconds()) / 60
    return delta <= margin_min

# === Fungsi presensi ===
def presensi(user_id, username, password, action):
    logging.info(f"[{user_id}] 🚀 Mulai {action}...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://dani.perhutani.co.id")
        time.sleep(3)

        # login
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
        time.sleep(5)

        # skip popup "Next" hingga "Finish"
        while True:
            try:
                next_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Next') or contains(text(),'Finish')]")
                txt = next_btn.text.strip().lower()
                next_btn.click()
                time.sleep(2)
                if "finish" in txt:
                    break
            except:
                break

        # klik presensi
        presensi_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")
        presensi_btn.click()
        time.sleep(5)

        # screenshot hasil
        ss_path = f"screenshots/{user_id}_{action}_{TODAY.strftime('%Y%m%d_%H%M')}.png"
        driver.save_screenshot(ss_path)
        logging.info(f"[{user_id}] 📸 Screenshot tersimpan: {ss_path}")

        logging.info(f"[{user_id}] ✅ {action} selesai.")
    except Exception as e:
        logging.error(f"[{user_id}] ❌ Error saat {action}: {e}")
    finally:
        driver.quit()

# === Loop user ===
for user in CONFIG["users"]:
    uid = user["id"]
    uname = os.getenv(user["secret_user"])
    upass = os.getenv(user["secret_pass"])

    if not uname or not upass:
        logging.warning(f"[{uid}] ⚠️ Username/password tidak ditemukan di Secrets.")
        continue

    if within_schedule(TODAY, user["check_in"], TIME_MARGIN):
        presensi(uid, uname, upass, "Check-In")
    elif within_schedule(TODAY, user["check_out"], TIME_MARGIN):
        presensi(uid, uname, upass, "Check-Out")
    else:
        logging.info(f"[{uid}] Skip (bukan jadwal user ini)")
