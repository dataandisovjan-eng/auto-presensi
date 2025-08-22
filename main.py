import sys
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Konfigurasi logging
log_filename = "presensi.log"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])

def setup_driver():
    """Inisialisasi WebDriver Chrome dengan webdriver-manager."""
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def login_and_presensi(driver, username, password):
    """Login dan melakukan presensi."""
    url_login = "https://dani.perhutani.co.id/login"
    try:
        logging.info("🌐 Buka halaman login...")
        driver.get(url_login)
        wait = WebDriverWait(driver, 30)

        username_input = None

        # Cari username input (utama dulu, kalau tidak ada, coba iframe)
        try:
            logging.info("🔎 Mencari field username di halaman utama...")
            username_input = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//input[@id='username' or @name='username' or @placeholder='Username']"))
            )
            logging.info("✅ Field username ditemukan di halaman utama.")
            driver.switch_to.default_content()
        except TimeoutException:
            logging.info("❌ Tidak ada di halaman utama, coba di iframe...")
            try:
                iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
                driver.switch_to.frame(iframe)
                logging.info("✅ Berhasil masuk ke iframe.")
                username_input = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@id='username' or @name='username' or @placeholder='Username']"))
                )
                logging.info("✅ Field username ditemukan di iframe.")
            except TimeoutException:
                logging.error("❌ Username input tidak ditemukan di halaman utama maupun iframe.")
                return False

        # Isi username dan password
        username_input.send_keys(username)
        password_input = driver.find_element(By.XPATH, "//input[@id='password' or @name='password' or @placeholder='Password']")
        password_input.send_keys(password)

        # Klik login
        logging.info("🔎 Cari tombol login...")
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Masuk') or @type='submit']"))
        )
        login_button.click()
        logging.info("✅ Klik tombol login.")

        driver.switch_to.default_content()

        # Handle popup (Next, Finish)
        try:
            wait_popup = WebDriverWait(driver, 15)
            while True:
                try:
                    next_btn = wait_popup.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'next')]")))
                    next_btn.click()
                    logging.info("⏭️ Klik Next.")
                    time.sleep(1)
                except TimeoutException:
                    break
            try:
                finish_btn = wait_popup.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]")))
                finish_btn.click()
                logging.info("🏁 Klik Finish.")
            except TimeoutException:
                logging.info("Tidak ada tombol Finish.")
        except Exception as e:
            logging.warning(f"Gagal handle popup: {e}")

        # Klik tombol presensi
        logging.info("⏳ Tunggu tombol presensi utama...")
        presensi_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn-presensi')]")))
        presensi_button.click()
        logging.info("✅ Klik tombol presensi.")
        time.sleep(5)

        # Cek hasil
        try:
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Presensi berhasil') or contains(text(), 'Anda telah melakukan presensi')]"))
            )
            logging.info("🎉 Presensi berhasil!")
            return True
        except TimeoutException:
            logging.warning("⚠️ Tidak ada pesan sukses, mungkin presensi gagal.")
            return False

    except Exception as e:
        logging.error(f"❌ Error saat login/presensi: {e}")
        return False

def main():
    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ USERNAME/PASSWORD tidak ditemukan di environment (Secrets).")
        return

    driver = setup_driver()
    if not driver:
        return

    try:
        login_and_presensi(driver, username, password)
    finally:
        logging.info("🚪 Tutup browser.")
        driver.quit()

if __name__ == "__main__":
    main()
