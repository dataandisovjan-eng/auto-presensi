import os
import sys
import time
import argparse
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ===============================
# Setup logging ke console + file
# ===============================
log_filename = f"presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, mode="w", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ===============================
# Fungsi presensi
# ===============================
def do_presensi(mode):
    username = os.getenv("USER1_USERNAME") or os.getenv("USER1") or os.getenv("ANDI_USERNAME")
    password = os.getenv("USER1_PASSWORD") or os.getenv("PASS1") or os.getenv("ANDI_PASSWORD")

    if not username or not password:
        logger.error("❌ Username/Password tidak ditemukan di secrets!")
        sys.exit(1)

    logger.info(f"✅ Kredensial ditemukan. Mencoba login sebagai: {username}")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    logger.info("⚙️ Mengatur driver...")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://dani.perhutani.co.id/login")
        logger.info("🌐 Buka halaman login...")

        # Isi username
        wait.until(EC.presence_of_element_located((By.NAME, "npk"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)

        # Klik login
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))).click()
        logger.info("✅ Klik tombol login.")

        # Tunggu tombol presensi
        logger.info("⏳ Menunggu tombol presensi utama...")
        presensi_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='presensi']")))

        # Klik presensi
        presensi_btn.click()
        logger.info(f"✅ Klik tombol presensi untuk {mode}.")

        # Tunggu notifikasi
        try:
            notif = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "swal2-popup")))
            logger.info(f"📢 Pesan notifikasi: {notif.text}")
        except:
            logger.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            screenshot_file = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_file)
            logger.info(f"📸 Screenshot disimpan: {screenshot_file}")

    except Exception as e:
        logger.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        driver.quit()
        logger.info("🚪 Keluar dari browser.")

# ===============================
# Main entry
# ===============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["check_in", "check_out"], required=True)
    args = parser.parse_args()

    do_presensi(args.mode)
