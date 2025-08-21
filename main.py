import os
import time
import logging
from datetime import datetime
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Konfigurasi logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Daftar user (pakai secret dari GitHub Actions)
USERS = [
    {
        "id": "user1",
        "name": "Pak Budi",
        "secret_user": "USER1_USERNAME",
        "secret_pass": "USER1_PASSWORD",
        "schedule": {
            "check_in": "05:30",
            "check_out": "16:05",
        },
    },
    {
        "id": "user2",
        "name": "Bu Sari",
        "secret_user": "USER2_USERNAME",
        "secret_pass": "USER2_PASSWORD",
        "schedule": {
            "check_in": "05:30",
            "check_out": "16:05",
        },
    },
]

def now_jakarta():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

def wait_and_click(driver, selector, timeout=10):
    """Coba klik tombol berdasarkan CSS selector"""
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        el.click()
        return True
    except:
        return False

def safe_find_input(driver, label="npk"):
    """Coba cari input field username dengan beberapa cara fallback"""
    try:
        return WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, label))
        )
    except:
        pass
    try:
        return WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, label))
        )
    except:
        pass
    try:
        # fallback: ambil input pertama
        return WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "input"))
        )
    except:
        raise Exception("❌ Tidak bisa menemukan field login NPK/username")

def presensi(user, mode):
    logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get("https://dani.perhutani.co.id/login")

        # Login
        username_field = safe_find_input(driver, "npk")
        username_field.send_keys(os.getenv(user["secret_user"]))

        password_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_field.send_keys(os.getenv(user["secret_pass"]))
        password_field.send_keys(Keys.RETURN)

        # Tunggu login selesai
        time.sleep(10)

        # Tutup semua popup (next/finish)
        while True:
            if wait_and_click(driver, "button.btn-success"):
                logging.info(f"[{user['name']}] ⏭️ Menutup popup...")
                time.sleep(2)
            else:
                break

        # Klik tombol presensi utama
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

def main(force_user=None, force_mode=None):
    now = now_jakarta()
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} (Asia/Jakarta)")

    for user in USERS:
        try:
            if force_user and user["id"] != force_user:
                logging.info(f"[{user['name']}] Skip (bukan user yang di-force)")
                continue

            schedule = user["schedule"]
            check_in_time = datetime.strptime(schedule["check_in"], "%H:%M").time()
            check_out_time = datetime.strptime(schedule["check_out"], "%H:%M").time()

            mode = None
            if force_mode:
                mode = force_mode
            elif check_in_time <= now.time() <= (datetime.combine(now.date(), check_in_time).replace(minute=check_in_time.minute+15)).time():
                mode = "check_in"
            elif check_out_time <= now.time() <= (datetime.combine(now.date(), check_out_time).replace(minute=check_out_time.minute+15)).time():
                mode = "check_out"

            if mode:
                presensi(user, mode)
            else:
                logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
        except Exception as e:
            logging.error(f"[{user['name']}] ❌ Error umum: {e}")

if __name__ == "__main__":
    force_user = os.getenv("FORCE_USER")
    force_mode = os.getenv("FORCE_MODE")
    main(force_user, force_mode)
