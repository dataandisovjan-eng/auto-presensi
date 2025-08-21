import os
import json
import pytz
import time
import logging
import datetime as dt
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("presensi.log", mode="w")]
)

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def is_holiday(today):
    """Cek hari libur nasional dari API (fallback: libur jika error)."""
    try:
        url = f"https://dayoffapi.vercel.app/api?year={today.year}&month={today.month}"
        res = requests.get(url, timeout=10).json()
        if isinstance(res, list):
            for item in res:
                if item.get("date") == today.strftime("%Y-%m-%d"):
                    return True
        return False
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

def wait_and_click(driver, selector, by=By.CSS_SELECTOR, max_attempts=5, delay=3):
    """Coba klik tombol popup (next/finish) jika muncul."""
    for attempt in range(max_attempts):
        try:
            btn = driver.find_element(by, selector)
            btn.click()
            time.sleep(2)
            return True
        except:
            time.sleep(delay)
    return False

def presensi(user, mode):
    logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get("https://dani.perhutani.co.id/login")
        time.sleep(5)

        # Input NPK (username) dan password
        driver.find_element(By.NAME, "npk").send_keys(os.getenv(user["secret_user"]))
        driver.find_element(By.NAME, "password").send_keys(os.getenv(user["secret_pass"]))
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
        time.sleep(10)

        # Tutup popup jika ada (next → finish)
        while wait_and_click(driver, "button.btn-success"):
            logging.info(f"[{user['name']}] ⏭️ Menutup popup...")

        # Klik tombol presensi
        if wait_and_click(driver, "button.btn-warning"):
            logging.info(f"[{user['name']}] ✅ Berhasil presensi ({mode})")
        else:
            logging.error(f"[{user['name']}] ❌ Tombol presensi tidak ditemukan")

        # Simpan screenshot
        os.makedirs("screenshots", exist_ok=True)
        driver.save_screenshot(f"screenshots/{user['id']}_{mode}.png")

    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")
    finally:
        driver.quit()

def main():
    cfg = load_config()
    tz = pytz.timezone(cfg["timezone"])
    now = dt.datetime.now(tz)
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({cfg['timezone']})")

    if is_holiday(now):
        logging.info("📌 Hari libur, presensi dilewati.")
        return

    force_user = os.getenv("FORCE_USER")
    force_mode = os.getenv("FORCE_MODE")

    for user in cfg["users"]:
        username = os.getenv(user["secret_user"])
        password = os.getenv(user["secret_pass"])
        if not username or not password:
            logging.info(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
            continue

        check_in = dt.datetime.strptime(user["check_in"], "%H:%M").time()
        check_out = dt.datetime.strptime(user["check_out"], "%H:%M").time()

        if force_user and force_user != user["id"]:
            continue

        if force_mode:
            presensi(user, force_mode)
            continue

        # Ada toleransi ±15 menit
        if abs(dt.timedelta(hours=now.hour, minutes=now.minute).total_seconds() -
               dt.timedelta(hours=check_in.hour, minutes=check_in.minute).total_seconds()) <= 900:
            presensi(user, "check_in")
        elif abs(dt.timedelta(hours=now.hour, minutes=now.minute).total_seconds() -
                 dt.timedelta(hours=check_out.hour, minutes=check_out.minute).total_seconds()) <= 900:
            presensi(user, "check_out")
        else:
            logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
