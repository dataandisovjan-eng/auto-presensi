import os
import json
import logging
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Setup logging
logging.basicConfig(
    filename="presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

tz = pytz.timezone(config["timezone"])
now = datetime.now(tz)
logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def presensi(user, username, password, mode):
    name = user["name"]
    logging.info(f"[{name}] 🌐 Membuka halaman login...")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1280, 800)

    try:
        driver.get("https://dani.perhutani.co.id/login")

        # Input NPK
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//input[@placeholder="NPK"]'))
        ).send_keys(username)

        # Input Password
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//input[@placeholder="Password"]'))
        ).send_keys(password)

        # Klik tombol Login
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"Login")]'))
        ).click()

        logging.info(f"[{name}] ✅ Login berhasil, mencoba presensi {mode}...")

        # Tunggu halaman setelah login
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Klik tombol presensi (contoh: teks "klik disini untuk presensi")
        try:
            tombol = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//a[contains(text(),"klik disini untuk presensi")]'))
            )
            tombol.click()
            logging.info(f"[{name}] ✅ Presensi {mode} berhasil!")
        except Exception:
            logging.warning(f"[{name}] ⚠️ Tombol presensi tidak ditemukan")

        driver.save_screenshot(f"screenshots/{user['id']}_{mode}.png")

    except Exception as e:
        logging.error(f"[{name}] ❌ Error saat presensi: {e}")
    finally:
        driver.quit()

# Buat folder screenshot
os.makedirs("screenshots", exist_ok=True)

# Jalankan untuk setiap user
for user in config["users"]:
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])

    if not username or not password:
        logging.warning(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
        continue

    check_in_time = datetime.strptime(user["check_in"], "%H:%M").time()
    check_out_time = datetime.strptime(user["check_out"], "%H:%M").time()

    if now.time().hour == check_in_time.hour and now.time().minute == check_in_time.minute:
        presensi(user, username, password, "check-in")
    elif now.time().hour == check_out_time.hour and now.time().minute == check_out_time.minute:
        presensi(user, username, password, "check-out")
    else:
        logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
