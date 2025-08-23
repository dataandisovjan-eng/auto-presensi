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
    """Inisialisasi WebDriver Chrome"""
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

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def main():
    """Fungsi utama"""
    username = os.environ.get('USER1_USERNAME')
    password = os.environ.get('USER1_PASSWORD')
    url_login = "https://dani.perhutani.co.id/login"

    if not username or not password:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan 'USER1_USERNAME' dan 'USER1_PASSWORD' sudah diatur.")
        return

    logging.info(f"✅ Kredensial ditemukan. Mencoba login sebagai: {username}")
    driver = setup_driver()
    if not driver:
        return

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get(url_login)
        wait = WebDriverWait(driver, 30)

        # Cari field username + password
        try:
            logging.info("🔎 Mencari field NPK...")
            username_input = wait.until(EC.element_to_be_clickable((By.XPATH,
                "//input[@placeholder='NPK'] | //input[contains(@id,'user') or contains(@name,'user') or contains(@placeholder,'user')]"
            )))
            logging.info("✅ Field NPK ditemukan.")

            password_input = driver.find_element(By.XPATH,
                "//input[@placeholder='Password'] | //input[contains(@id,'pass') or contains(@name,'pass') or contains(@type,'password')]"
            )
        except TimeoutException:
            logging.error("❌ Gagal menemukan field login.")
            return

        # Isi login
        username_input.send_keys(username)
        password_input.send_keys(password)
        logging.info("🔎 Mencari tombol login...")
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH,
            "//button[contains(text(),'Login') or contains(text(),'Masuk') or @type='submit']"
        )))
        login_button.click()
        logging.info("✅ Klik tombol login.")

        driver.switch_to.default_content()
        logging.info("✅ Kembali ke konten utama.")

        # Tangani popup tour
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        try:
            wait_for_popup = WebDriverWait(driver, 10)
            next_clicked_count = 0
            max_next_clicks = 10  # Batas agar tidak infinite loop

            while next_clicked_count < max_next_clicks:
                try:
                    next_button = wait_for_popup.until(EC.element_to_be_clickable((By.XPATH,
                        "//*[contains(text(),'Next') or contains(text(),'Selanjutnya') or .//i[contains(@class,'fa-arrow-right')]]"
                    )))
                    next_button.click()
                    next_clicked_count += 1
                    logging.info(f"⏭️ Klik Next (total: {next_clicked_count})")
                    time.sleep(1)
                except TimeoutException:
                    logging.info("Tidak ada tombol 'Next' lagi.")
                    break

            # Cari tombol Finish / Selesai
            try:
                finish_button = wait_for_popup.until(EC.element_to_be_clickable((By.XPATH,
                    "//*[contains(text(),'Finish') or contains(text(),'Selesai') or .//i[contains(@class,'fa-flag-checkered')] or contains(@class,'btn-finish')]"
                )))
                finish_button.click()
                logging.info("🏁 Klik Finish/Selesai.")
            except TimeoutException:
                logging.info("⚠️ Tidak menemukan tombol Finish, lanjutkan tanpa menutup popup.")

        except Exception as e:
            logging.warning(f"Gagal menangani popup: {e}")

        # Cari tombol presensi
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class,'btn-presensi')] | //a[contains(@href,'/presensi')]"))
        )
        logging.info("✅ Tombol presensi utama ditemukan.")
        presensi_button.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")
        time.sleep(5)

        # Cek berhasil/tidak
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH,
                    "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi')]"
                ))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        logging.info("🚪 Keluar dari browser.")
        driver.quit()

if __name__ == "__main__":
    main()
