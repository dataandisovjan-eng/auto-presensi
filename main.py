import sys
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Konfigurasi logging
log_filename = "presensi.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

def setup_driver():
    """Mengatur dan menginisialisasi WebDriver dengan webdriver-manager."""
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")

        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options,
        )
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def main():
    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")
    url_login = "https://dani.perhutani.co.id/login"

    if not username or not password:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan USER1_USERNAME dan USER1_PASSWORD sudah diatur di Secrets.")
        return

    logging.info(f"✅ Kredensial ditemukan. Mencoba login sebagai: {username}")

    driver = setup_driver()
    if not driver:
        return

    try:
        logging.info("🌐 Membuka halaman login...")
        driver.get(url_login)

        wait = WebDriverWait(driver, 30)
        username_input = None

        # Coba cari di halaman utama
        try:
            logging.info("🔎 Mencari field username di halaman utama...")
            username_input = wait.until(
                EC.element_to_be_clickable((By.XPATH,
                    "//input[@id='username' or @name='username' or @placeholder='Username']"
                    " | //input[contains(@type, 'text') and contains(@class, 'form-control')]"
                ))
            )
            logging.info("✅ Field username ditemukan di halaman utama.")
            driver.switch_to.default_content()
        except TimeoutException:
            logging.info("❌ Field username tidak ditemukan di halaman utama. Mencoba mencari di dalam iframe...")
            try:
                iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
                driver.switch_to.frame(iframe)
                logging.info("✅ Berhasil beralih ke iframe.")
                username_input = wait.until(
                    EC.element_to_be_clickable((By.XPATH,
                        "//input[@id='username' or @name='username' or @placeholder='Username']"
                        " | //input[contains(@type, 'text') and contains(@class, 'form-control')]"
                    ))
                )
                logging.info("✅ Field username ditemukan di dalam iframe.")
            except TimeoutException:
                logging.error("❌ Gagal menemukan iframe atau field username di dalamnya.")
                raise

        if username_input:
            username_input.send_keys(username)
            password_input = driver.find_element(By.XPATH,
                "//input[@id='password' or @name='password' or @placeholder='Password']"
                " | //input[contains(@type, 'password') and contains(@class, 'form-control')]"
            )
            password_input.send_keys(password)

            logging.info("🔎 Mencari tombol login...")
            login_button = wait.until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[contains(text(), 'Login') or contains(text(), 'Masuk') or @type='submit']"
                ))
            )
            login_button.click()
            logging.info("✅ Klik tombol login.")

        driver.switch_to.default_content()
        logging.info("✅ Kembali ke konten utama.")

        # Tangani pop-up
        try:
            logging.info("🔎 Mengecek apakah ada pop-up...")
            popup_wait = WebDriverWait(driver, 15)
            while True:
                try:
                    next_button = popup_wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'next')]"))
                    )
                    next_button.click()
                    logging.info("⏭️ Klik Next.")
                    time.sleep(1)
                except TimeoutException:
                    break
            finish_button = popup_wait.until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]"))
            )
            finish_button.click()
            logging.info("🏁 Klik Finish/Selesai.")
        except TimeoutException:
            logging.info("ℹ️ Tidak ada pop-up yang perlu ditutup.")

        # Tombol presensi
        logging.info("⏳ Menunggu tombol presensi...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn-presensi')]"))
        )
        presensi_button.click()
        logging.info("✅ Klik tombol presensi utama.")
        time.sleep(5)

        # Verifikasi
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH,
                    "//*[contains(text(), 'Presensi berhasil') or contains(text(), 'Anda telah melakukan presensi')]"
                ))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak muncul. Periksa manual.")

    except Exception as e:
        logging.error(f"❌ Terjadi error: {e}")
    finally:
        if driver:
            logging.info("🚪 Keluar dari browser.")
            driver.quit()

if __name__ == "__main__":
    main()
