import os
import json
import time
import logging
from datetime import datetime, timedelta
import pytz
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Setup logging ke file
os.makedirs("logs", exist_ok=True)
os.makedirs("screenshots", exist_ok=True)
logging.basicConfig(
    filename="logs/presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def log_console(msg):
    """Cetak log ke console + tulis ke file"""
    print(msg, flush=True)
    logging.info(msg)

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def is_holiday(today, timezone):
    """Cek libur nasional via API"""
    try:
        year = today.year
        url = f"https://dayoffapi.vercel.app/api?year={year}&tz={timezone}"
        res = requests.get(url, timeout=10)
        data = res.json()
        holidays = [h["date"] for h in data.get("holidays", [])]
        return today.strftime("%Y-%m-%d") in holidays
    except Exception as e:
        log_console(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

def do_presensi(user_id, username, password, jenis):
    """Automasi login + presensi"""
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.get("https://dani.perhutani.co.id")
        time.sleep(3)

        # Login
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(5)

        # Tutup semua popup "Next" kalau ada
        while True:
            try:
                next_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Next')]")
                next_btn.click()
                time.sleep(1)
            except:
                break

        # Klik tombol "Klik disini untuk presensi" (utama)
        presensi_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")
        presensi_btn.click()
        time.sleep(3)

        # Klik lagi di popup terakhir
        final_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")
        final_btn.click()
        time.sleep(3)

        # Screenshot bukti
        filename = f"screenshots/{user_id}_{jenis}.png"
        driver.save_screenshot(filename)
        log_console(f"[{user_id}] ✅ Presensi {jenis} BERHASIL, screenshot: {filename}")

    except Exception as e:
        log_console(f"[{user_id}] ❌ Error saat presensi {jenis}: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

def main():
    config = load_config()
    tz = pytz.timezone(config["timezone"])
    now = datetime.now(tz)
    today = now.date()
    log_console(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({config['timezone']})")

    # Skip weekend / libur
    if now.weekday() >= 5:  # Sabtu(5) Minggu(6)
        log_console("📌 Skip (hari weekend)")
        return
    if is_holiday(now, config["timezone"]):
        log_console("📌 Skip (hari libur nasional)")
        return

    for user in config["users"]:
        user_id = user["id"]
        username = os.getenv(user["secret_user"])
        password = os.getenv(user["secret_pass"])
        if not username or not password:
            log_console(f"[{user_id}] ⚠️ Username/password tidak ditemukan di Secrets")
            continue

        # Jadwal check in/out
        check_in_time = datetime.strptime(user["check_in"], "%H:%M").time()
        check_out_time = datetime.strptime(user["check_out"], "%H:%M").time()

        margin = timedelta(minutes=10)

        # Cek check in
        if check_in_time <= now.time() <= (datetime.combine(today, check_in_time) + margin).time():
            do_presensi(user_id, username, password, "checkin")
        # Cek check out
        elif check_out_time <= now.time() <= (datetime.combine(today, check_out_time) + margin).time():
            do_presensi(user_id, username, password, "checkout")
        else:
            log_console(f"[{user_id}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
