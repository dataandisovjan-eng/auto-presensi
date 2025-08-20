import os
import json
import time
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Fungsi login & presensi
def presensi(username, password, mode, user_name):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://dani.perhutani.co.id")

        # Login
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Handle pop-up Next → Finish
        try:
            while True:
                next_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(.,'Next') or contains(.,'Finish')]"))
                )
                next_btn.click()
                time.sleep(1)
                if "Finish" in next_btn.text:
                    break
        except:
            pass  # Kalau tidak ada pop-up

        # Klik tombol presensi utama
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(.,'Klik Disini untuk Presensi')]"))
        ).click()

        # Klik tombol presensi di pop-up konfirmasi
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(.,'Klik Disini untuk Presensi')]"))
        ).click()

        # Screenshot bukti
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_name}_{mode}_{ts}.png"
        driver.save_screenshot(filename)
        print(f"✅ {user_name} berhasil presensi {mode}. Screenshot: {filename}")

    except Exception as e:
        print(f"❌ Error {user_name} {mode}: {e}")
    finally:
        driver.quit()

# --- MAIN ---
with open("config.json", "r") as f:
    config = json.load(f)

timezone = pytz.timezone(config["timezone"])
now = datetime.now(timezone)
today_hhmm = now.strftime("%H:%M")

for user in config["users"]:
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])

    if not username or not password:
        print(f"⚠️ Secrets untuk {user['name']} belum di-set")
        continue

    if today_hhmm == user["check_in"]:
        presensi(username, password, "pagi", user["name"])
    elif today_hhmm == user["check_out"]:
        presensi(username, password, "sore", user["name"])
    else:
        print(f"ℹ️ Bukan jadwal presensi untuk {user['name']} (sekarang {today_hhmm})")
