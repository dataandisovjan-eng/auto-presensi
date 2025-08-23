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
from selenium.common.exceptions import TimeoutException, WebDriverException

# Konfigurasi logging
log_filename = "presensi.log"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])

def save_screenshot(driver, name="error_screenshot"):
    """Simpan screenshot dengan timestamp"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.png"
    try:
        driver.save_screenshot(filename)
        logging.info(f"📸 Screenshot disimpan: {filename}")
    except Exception as e:
        logging.error(f"❌ Gagal menyimpan screenshot: {e}")

def setup_driver():
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

def close_all_popups(driver):
    """Menutup semua popup/modal yang menghalangi klik"""
    logging.info("🛑 Periksa modal/pop-up aktif...")
    try:
        modals = driver.find_elements(By.XPATH, "//div[contains(@class,'modal') and contains(@class,'show')]")
        for modal in modals:
            try:
                close_btn = modal.find_element(By.XPATH, ".//button[contains(@class,'close') or @data-dismiss='modal']")
                close_btn.click()
                logging.info("❎ Modal ditutup dengan tombol X.")
                time.sleep(1)
            except:
                driver.execute_script("arguments[0].remove();", modal)
                logging.info("❎ Modal dihapus pakai JS.")
    except Exception as e:
        logging.warning(f"⚠️ Tidak ada modal yang perlu ditutup: {e}")

def main():
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

        # Login
        username_input = wait.until(EC.element_to_be_clickable((By.XPATH,
            "//input[@placeholder='NPK'] | //input[contains(@id,'user') or contains(@name,'user')]"
        )))
        password_input = driver.find_element(By.XPATH,
            "//input[@placeholder='Password'] | //input[@type='password']"
        )
        username_input.send_keys(username)
        password_input.send_keys(password)
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH,
            "//button[contains(text(),'Login') or contains(text(),'Masuk') or @type='submit']"
        )))
        login_button.click()
        logging.info("✅ Klik tombol login.")

        driver.switch_to.default_content()

        # Tutup tour popup
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        next_clicked_count = 0
        max_next_clicks = 10
        while next_clicked_count < max_next_clicks:
            try:
                next_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH,
                    "//*[contains(text(),'Next') or contains(text(),'Selanjutnya')]"
                )))
                next_button.click()
                next_clicked_count += 1
                logging.info(f"⏭️ Klik Next (total: {next_clicked_count})")
                time.sleep(1)
            except TimeoutException:
                break
        try:
            finish_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH,
                "//*[contains(text(),'Finish') or contains(text(),'Selesai')]"
            )))
            finish_button.click()
            logging.info("🏁 Klik Finish/Selesai.")
        except TimeoutException:
            logging.info("⚠️ Tidak menemukan tombol Finish, lanjut.")

        # Tutup modal lain sebelum klik presensi
        close_all_popups(driver)

        # Klik presensi
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/presensi')]"))
        )

        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]")))
            presensi_button.click()
            logging.info("✅ Klik: Tombol Presensi Utama.")
        except Exception as e:
            logging.warning(f"⚠️ Gagal klik normal ({e}), coba pakai JavaScript...")
            driver.execute_script("arguments[0].click();", presensi_button)
            logging.info("✅ Klik tombol presensi via JavaScript.")

        time.sleep(3)

        # Cek berhasil
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH,
                    "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi')]"
                ))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            save_screenshot(driver, "presensi_notif_missing")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        save_screenshot(driver, "fatal_error")
    finally:
        logging.info("🚪 Keluar dari browser.")
        driver.quit()

if __name__ == "__main__":
    main()
