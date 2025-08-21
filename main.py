import os
import json
import time
import logging
import pytz
import datetime as dt
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("presensi.log"), logging.StreamHandler()]
)

# === Load Config ===
with open("config.json", "r") as f:
    CONFIG = json.load(f)

TZ = pytz.timezone(CONFIG["timezone"])

# === Helpers ===
def screenshot(driver, filename):
    os.makedirs("screenshots", exist_ok=True)
    driver.save_screenshot(os.path.join("screenshots", filename))

def wait_and_click(driver, by, value, timeout=10):
    try:
        btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        btn.click()
        return True
    except Exception:
        return False

# === Holiday Check (fallback selalu False kalau error) ===
def is_holiday(today):
    try:
        resp = requests.get(
            f"https://raw.githubusercontent.com/guangrei/APIHariLibur/master/calendar.json"
        )
        data = resp.json()
        return data.get(today.strftime("%Y-%m-%d"), {}).get("holiday", False)
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

# === Login & Presensi ===
def handle_popups(driver, user):
    while True:
        if wait_and_click(driver, By.XPATH, "//button[contains(., 'Next')]", timeout=3):
            logging.info(f"[{user['name']}] ⏭️ Popup Next ditutup")
            time.sleep(1)
            continue
        elif wait_and_click(driver, By.XPATH, "//button[contains(., 'Finish')]", timeout=3):
            logging.info(f"[{user['name']}] ✅ Popup Finish ditutup")
            time.sleep(1)
            break
        else:
            break

def login(driver, user):
    username = os.getenv(f"{user['id'].upper()}_ID")
    password = os.getenv(f"{user['id'].upper()}_PASS")

    driver.get(CONFIG["base_url"])
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "username"))
    ).send_keys(username)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "password"))
    ).send_keys(password)

    wait_and_click(driver, By.XPATH, "//button[contains(., 'Login')]")
    logging.info(f"[{user['name']}] ✅ Berhasil login")
    screenshot(driver, f"{user['id']}_login.png")

def do_presensi(driver, user, mode):
    try:
        handle_popups(driver, user)

        if wait_and_click(driver, By.XPATH, "//button[contains(., 'klik disini untuk presensi')]", timeout=10):
            logging.info(f"[{user['name']}] 🟠 Tombol presensi utama diklik")
            screenshot(driver, f"{user['id']}_{mode}_main.png")

            if wait_and_click(driver, By.XPATH, "//button[contains(., 'klik disini untuk presensi')]", timeout=10):
                logging.info(f"[{user['name']}] ✅ Berhasil presensi {mode}")
                screenshot(driver, f"{user['id']}_{mode}_done.png")
            else:
                logging.error(f"[{user['name']}] ❌ Popup presensi tidak muncul")
        else:
            logging.error(f"[{user['name']}] ❌ Tombol presensi utama tidak ditemukan")

    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")
        screenshot(driver, f"{user['id']}_{mode}_error.png")

def run_for_user(user, now, force_mode=None):
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_opts)

    try:
        login(driver, user)

        check_in = dt.datetime.strptime(user["check_in"], "%H:%M").time()
        check_out = dt.datetime.strptime(user["check_out"], "%H:%M").time()
        tolerance = dt.timedelta(minutes=CONFIG.get("tolerance_minutes", 5))

        if force_mode:
            do_presensi(driver, user, force_mode)
        else:
            if check_in <= now.time() <= (dt.datetime.combine(now.date(), check_in) + tolerance).time():
                do_presensi(driver, user, "check_in")
            elif check_out <= now.time() <= (dt.datetime.combine(now.date(), check_out) + tolerance).time():
                do_presensi(driver, user, "check_out")
            else:
                logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
    finally:
        driver.quit()

# === Main ===
if __name__ == "__main__":
    now = dt.datetime.now(TZ)
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({CONFIG['timezone']})")

    if is_holiday(now):
        logging.info("📅 Hari libur, presensi dilewati.")
        exit()

    force_user = os.getenv("FORCE_USER")
    force_mode = os.getenv("FORCE_MODE")

    for user in CONFIG["users"]:
        if force_user and user["id"] != force_user:
            continue
        run_for_user(user, now, force_mode)
