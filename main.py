import os
import time
import json
import logging
import pytz
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# === Setup Logging ===
os.makedirs("logs", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)
log_file = f"logs/presensi_{datetime.date.today()}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# === Load Config ===
with open("config.json", "r") as f:
    config = json.load(f)

TIMEZONE = pytz.timezone(config.get("timezone", "Asia/Jakarta"))
BASE_URL = "https://dani.perhutani.co.id"

# === Cek Hari Libur Nasional ===
def is_holiday(today):
    try:
        year = today.year
        url = f"https://raw.githubusercontent.com/guangrei/APIHariLibur/main/{year}.json"
        res = requests.get(url, timeout=10)
        holidays = res.json()
        today_str = today.strftime("%Y-%m-%d")
        return today_str in holidays
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

# === Login + Presensi ===
def do_presensi(username, password, user_name, mode="checkin"):
    logging.info(f"[{user_name}] 🚀 Mulai presensi {mode}...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        driver.get(BASE_URL)
        time.sleep(2)

        # Login
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        # Handle pop-up "Next" jika ada
        while True:
            try:
                btn_next = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
                btn_next.click()
                time.sleep(1)
            except:
                break
        try:
            btn_finish = driver.find_element(By.XPATH, "//button[contains(text(), 'Finish')]")
            btn_finish.click()
            time.sleep(1)
        except:
            pass

        # Klik tombol presensi utama (warna oranye)
        try:
            presensi_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Klik disini untuk presensi')]")
            presensi_btn.click()
            time.sleep(2)
        except Exception as e:
            logging.error(f"[{user_name}] ❌ Gagal menemukan tombol presensi: {e}")
            return

        # Popup konfirmasi terakhir
        try:
            popup_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Klik disini untuk presensi')]")
            popup_btn.click()
            time.sleep(2)
        except:
            logging.warning(f"[{user_name}] ⚠️ Tidak menemukan tombol presensi di popup")

        # Screenshot hasil
        screenshot_path = f"screenshots/{user_name}_{mode}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_path)
        logging.info(f"[{user_name}] 📸 Screenshot disimpan: {screenshot_path}")

        logging.info(f"[{user_name}] ✅ Presensi {mode} selesai")
    except Exception as e:
        logging.error(f"[{user_name}] ❌ Error saat presensi: {e}")
    finally:
        driver.quit()

# === Main Run ===
def main():
    now = datetime.datetime.now(TIMEZONE)
    today = now.date()
    now_str = now.strftime("%H:%M")
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({TIMEZONE})")

    if now.weekday() >= 5:
        logging.info("📌 Weekend, skip presensi")
        return
    if is_holiday(today):
        logging.info("📌 Hari libur nasional, skip presensi")
        return

    for user in config["users"]:
        username = os.getenv(user["secret_user"])
        password = os.getenv(user["secret_pass"])
        if not username or not password:
            logging.warning(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
            continue

        if now_str == user["check_in"]:
            do_presensi(username, password, user["name"], "checkin")
        elif now_str == user["check_out"]:
            do_presensi(username, password, user["name"], "checkout")
        else:
            logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
