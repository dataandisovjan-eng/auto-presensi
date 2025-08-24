import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- Ambil secrets ---
def get_credentials(user: str):
    username = os.getenv(f"{user}_USERNAME")
    password = os.getenv(f"{user}_PASSWORD")
    if not username or not password:
        logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user}!")
        return None, None
    return username, password

# --- Setup browser ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-geolocation")  # biar popup lokasi tidak ganggu
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1280, 1024)
    return driver

# --- Proses Presensi ---
def presensi(user: str):
    logging.info(f"⏰ Mulai proses presensi untuk {user}...")

    username, password = get_credentials(user)
    if not username or not password:
        return False

    driver = setup_driver()
    try:
        logging.info(f"🌐 [{user}] Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id/")

        # isi username
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "npk"))).send_keys(username)
        # isi password
        driver.find_element(By.NAME, "password").send_keys(password)
        # klik login
        driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
        logging.info(f"🔐 [{user}] Login dikirim.")

        # --- Cari tombol presensi utama (box oranye) ---
        logging.info(f"⏳ [{user}] Menunggu tombol presensi utama...")
        try:
            presensi_button = WebDriverWait(driver, 40).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//*[contains(text(),'Klik Disini Untuk Presensi')]/ancestor::div[contains(@class,'small-box')]"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", presensi_button)
            time.sleep(1)
            presensi_button.click()
            logging.info(f"🟠 [{user}] Klik tombol presensi utama.")
        except TimeoutException:
            logging.error(f"❌ [{user}] Tombol presensi utama tidak ditemukan.")
            screenshot_file = f"presensi_btn_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_file)
            with open(f"page_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.warning(f"📸 Screenshot dan HTML dump disimpan.")
            return False

        # --- Handle popup lokasi (jika muncul) ---
        try:
            popup_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk Presensi')]"))
            )
            popup_button.click()
            logging.info(f"📍 [{user}] Popup lokasi ditangani, presensi diklik.")
        except TimeoutException:
            logging.info(f"✅ [{user}] Tidak ada popup lokasi, lanjut.")

        # --- Konfirmasi berhasil ---
        time.sleep(3)
        try:
            checkin_status = driver.find_element(By.XPATH, "//*[contains(text(),'Sudah Check In') or contains(text(),'Sudah Check Out')]")
            logging.info(f"✅ [{user}] Presensi berhasil: {checkin_status.text}")
        except NoSuchElementException:
            logging.warning(f"⚠️ [{user}] Tidak menemukan teks konfirmasi presensi, cek manual.")
            driver.save_screenshot(f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    except Exception as e:
        logging.error(f"❌ [{user}] Terjadi kesalahan: {e}")
        return False
    finally:
        logging.info(f"🚪 [{user}] Keluar dari browser.")
        driver.quit()

    return True

# --- Main run ---
if __name__ == "__main__":
    users = ["USER1", "USER2"]  # bisa ditambah USER3, dst
    success = True
    for u in users:
        ok = presensi(u)
        if not ok:
            success = False

    if not success:
        exit(1)
