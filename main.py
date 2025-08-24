import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ========== Logging setup ==========
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ========== Users & Secrets ==========
USERS = {
    "USER1": {
        "username": os.getenv("USER1"),
        "password": os.getenv("PASS1"),
    },
    "USER2": {
        "username": os.getenv("USER2_USERNAME"),
        "password": os.getenv("USER2_PASSWORD"),
    }
}

LOGIN_URL = "https://dani.perhutani.co.id/"

# ========== Browser Setup ==========
def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    options.add_argument("--disable-notifications")
    return webdriver.Chrome(options=options)

# ========== Proses Presensi ==========
def presensi(user_key, creds):
    username, password = creds["username"], creds["password"]

    if not username or not password:
        logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user_key}!")
        return False

    driver = setup_driver()
    driver.set_window_size(1280, 800)

    try:
        logging.info(f"⏰ Mulai proses presensi untuk {user_key}...")

        # buka halaman login
        driver.get(LOGIN_URL)
        logging.info(f"🌐 [{user_key}] Membuka halaman login...")

        # tunggu input username (NPK)
        try:
            npk_input = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "npk"))
            )
            pwd_input = driver.find_element(By.NAME, "password")
        except TimeoutException:
            logging.error(f"❌ [{user_key}] Field login tidak ditemukan.")
            return False

        npk_input.clear()
        npk_input.send_keys(username)
        pwd_input.clear()
        pwd_input.send_keys(password)

        # tombol login
        try:
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
            login_btn.click()
        except NoSuchElementException:
            logging.error(f"❌ [{user_key}] Tombol login tidak ditemukan.")
            return False

        logging.info(f"🔐 [{user_key}] Login dikirim.")

        # tunggu tombol presensi utama
        try:
            presensi_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Klik Disini Untuk Presensi') or contains(.,'Presensi')]"))
            )
        except TimeoutException:
            logging.error(f"❌ [{user_key}] Tombol presensi utama tidak ditemukan.")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            driver.save_screenshot(f"presensi_btn_missing_{ts}.png")
            return False

        logging.info(f"✅ [{user_key}] Klik tombol presensi utama.")
        presensi_btn.click()
        time.sleep(2)

        # popup lokasi → cari tombol "Klik disini untuk Presensi"
        try:
            lokasi_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk Presensi') or contains(.,'Presensi')]"))
            )
            lokasi_btn.click()
            logging.info(f"📍 [{user_key}] Klik konfirmasi presensi (popup lokasi).")
        except TimeoutException:
            logging.warning(f"⚠️ [{user_key}] Popup lokasi tidak muncul, lanjutkan.")

        # tunggu status berubah
        time.sleep(3)
        logging.info(f"🎉 [{user_key}] Presensi berhasil (Check-in/Check-out).")
        return True

    except Exception as e:
        logging.error(f"❌ [{user_key}] Terjadi kesalahan: {e}")
        return False

    finally:
        logging.info(f"🚪 [{user_key}] Keluar dari browser.")
        driver.quit()

# ========== Main ==========
if __name__ == "__main__":
    success = True
    for user_key, creds in USERS.items():
        if not presensi(user_key, creds):
            success = False

    if not success:
        exit(1)
