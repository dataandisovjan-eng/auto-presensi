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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(
    filename="presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def cek_hari_libur(tanggal: str) -> bool:
    """Cek apakah tanggal termasuk hari libur nasional"""
    try:
        url = f"https://dayoffapi.vercel.app/api?date={tanggal}"
        res = requests.get(url, timeout=10)
        data = res.json()
        if isinstance(data, dict):
            return data.get("holiday", False)
        elif isinstance(data, list) and len(data) > 0:
            return data[0].get("holiday", False)
    except Exception as e:
        logging.warning(f"⚠️ Gagal cek API Hari Libur: {e}")
    return False

def presensi(user, username, password, mode):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id/login")

        wait = WebDriverWait(driver, 20)

        # Input NPK (username)
        npk_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        npk_input.send_keys(username)

        # Input password
        pass_input = driver.find_element(By.NAME, "password")
        pass_input.send_keys(password)

        # Klik login
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(3)

        # Klik tombol presensi
        if mode == "check-in":
            tombol = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Check In')]")))
        else:
            tombol = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Check Out')]")))

        tombol.click()
        logging.info(f"[{user['name']}] ✅ Presensi {mode} berhasil")

        # Simpan screenshot
        os.makedirs("screenshots", exist_ok=True)
        ss_file = f"screenshots/{user['id']}_{mode}_{int(time.time())}.png"
        driver.save_screenshot(ss_file)

        driver.quit()
    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")
        os.makedirs("screenshots", exist_ok=True)
        ss_file = f"screenshots/{user['id']}_{mode}_ERROR_{int(time.time())}.png"
        try:
            driver.save_screenshot(ss_file)
        except:
            pass
        if 'driver' in locals():
            driver.quit()

def main():
    config = load_config()
    tz = pytz.timezone(config.get("timezone", "Asia/Jakarta"))
    now = datetime.now(tz)
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

    # Skip kalau hari libur
    if cek_hari_libur(now.strftime("%Y-%m-%d")):
        logging.info("📅 Hari ini libur nasional, presensi dilewati.")
        return

    # Input manual dari workflow_dispatch
    force_user = os.getenv("FORCE_USER", "").strip()
    force_mode = os.getenv("FORCE_MODE", "").strip().lower()

    for user in config["users"]:
        username = os.getenv(user["secret_user"])
        password = os.getenv(user["secret_pass"])

        if not username or not password:
            logging.warning(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
            continue

        # Mode manual
        if force_user and force_mode:
            if user["id"] == force_user:
                presensi(user, username, password, force_mode)
            else:
                logging.info(f"[{user['name']}] Skip (bukan user yang dipaksa)")
            continue

        # Mode otomatis (jadwal)
        check_in_time = datetime.strptime(user["check_in"], "%H:%M").time()
        check_out_time = datetime.strptime(user["check_out"], "%H:%M").time()

        if now.time().hour == check_in_time.hour and now.time().minute == check_in_time.minute:
            presensi(user, username, password, "check-in")
        elif now.time().hour == check_out_time.hour and now.time().minute == check_out_time.minute:
            presensi(user, username, password, "check-out")
        else:
            logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
