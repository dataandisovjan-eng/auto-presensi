import sys
import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Konfigurasi logging
log_filename = f"presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    handlers=[
                        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
                        logging.StreamHandler(sys.stdout)
                    ])

def setup_driver():
    """Setup Chrome WebDriver."""
    try:
        logging.info("⚙️ Mengatur driver...")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 1  # izinkan lokasi otomatis
        })
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def presensi(user: str, username: str, password: str):
    """Proses presensi untuk user tertentu."""
    url_login = "https://dani.perhutani.co.id/login"
    driver = setup_driver()
    if not driver:
        return False

    try:
        wait = WebDriverWait(driver, 30)
        logging.info(f"🌐 [{user}] Membuka halaman login...")
        driver.get(url_login)

        # Login
        username_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']")))
        password_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Password']")))
        username_input.send_keys(username)
        password_input.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Login') or contains(text(),'Masuk') or @type='submit']")))
        login_button.click()
        logging.info(f"🔐 [{user}] Login dikirim.")

        # Tunggu tombol presensi utama
        logging.info(f"⏳ [{user}] Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Klik Disini Untuk Presensi')]"))
        )
        presensi_button.click()
        logging.info(f"🟠 [{user}] Klik tombol presensi utama.")

        time.sleep(3)

        # Jika muncul popup, klik tombol presensi di dalam popup
        try:
            popup_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Klik Disini Untuk Presensi')]"))
            )
            popup_button.click()
            logging.info(f"🟠 [{user}] Klik tombol presensi di popup.")
        except TimeoutException:
            logging.info(f"ℹ️ [{user}] Tidak ada popup presensi tambahan.")

        # Verifikasi Check In / Check Out berhasil
        try:
            confirm = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Sudah Check In') or contains(text(),'Sudah Check Out')]"))
            )
            logging.info(f"🎉 [{user}] Presensi berhasil: {confirm.text}")
        except TimeoutException:
            # Screenshot jika gagal menemukan konfirmasi
            screenshot_file = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_file)
            logging.warning(f"⚠️ [{user}] Konfirmasi presensi tidak ditemukan. Screenshot: {screenshot_file}")

    except Exception as e:
        logging.error(f"❌ [{user}] Terjadi kesalahan: {e}")
        return False
    finally:
        driver.quit()
        logging.info(f"🚪 [{user}] Keluar dari browser.")

    return True

def main():
    logging.info("⏰ Mulai proses presensi...")

    # Ambil kredensial dari Secrets
    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")
        sys.exit(1)

    success = presensi("USER1", username, password)
    if success:
        logging.info("✅ Presensi selesai dengan sukses.")
    else:
        logging.error("❌ Presensi gagal.")

if __name__ == "__main__":
    main()
