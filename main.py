import os
import sys
import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException

# === Konfigurasi Logging ===
os.makedirs("artifacts", exist_ok=True)
log_filename = f"artifacts/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# === Setup Driver ===
def setup_driver():
    """Mengatur dan menginisialisasi WebDriver."""
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        chrome_options.add_argument("--log-level=3")  # Matikan logging dari browser

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# === Fungsi Login & Presensi ===
def login_and_presensi(username, password, mode="check_in"):
    url_login = "https://dani.perhutani.co.id/login"
    driver = setup_driver()
    if not driver:
        return

    try:
        driver.get(url_login)
        wait = WebDriverWait(driver, 30)

        # === Hapus modal popup announcement jika ada ===
        try:
            modal = driver.find_element(By.ID, "announcement")
            if modal.is_displayed():
                driver.execute_script("arguments[0].remove();", modal)
                logging.info("❎ Modal login dihapus pakai JS.")
        except Exception:
            pass

        # === Cari input NPK & Password ===
        logging.info("🔎 Cari field login...")
        username_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='NPK' or contains(@name,'username') or contains(@id,'username')]")
        ))
        password_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Password' or @type='password']")
        ))
        username_input.send_keys(username)
        password_input.send_keys(password)

        # Klik tombol login
        login_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Login') or contains(text(),'Masuk') or @type='submit']")
        ))
        login_button.click()
        logging.info("✅ Klik tombol login.")

        # === Tutup popup Next/Finish (jika ada) ===
        try:
            next_count = 0
            while True:
                try:
                    next_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(),'Next') or contains(text(),'Selanjutnya')]")
                    ))
                    next_button.click()
                    next_count += 1
                    logging.info(f"⏭️ Klik Next ({next_count})")
                    time.sleep(1)
                except TimeoutException:
                    break
            try:
                finish_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                    (By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]")
                ))
                finish_button.click()
                logging.info("🏁 Klik Finish.")
            except TimeoutException:
                logging.info("⚠️ Tidak menemukan tombol Finish, lanjut.")
        except Exception as e:
            logging.warning(f"⚠️ Popup tidak tertutup sempurna: {e}")

        # === Klik tombol presensi utama ===
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')] | //a[contains(@class, 'btn-presensi')]"))
        )
        try:
            presensi_button.click()
            logging.info("✅ Klik tombol presensi utama.")
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", presensi_button)
            logging.info("✅ Klik tombol presensi dengan JS.")

        # === Mengisi aktivitas dan klik simpan ===
        logging.info("⏳ Menunggu field input aktivitas...")
        try:
            activity_input = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Isi disini'] | //textarea[contains(@name, 'activity')]"))
            )
            # Mengisi teks aktivitas sesuai permintaan user
            activity_input.send_keys("Persiapan apel pagi")
            logging.info("✅ Teks aktivitas diisi.")

            save_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Simpan')]"))
            )
            save_button.click()
            logging.info("✅ Klik tombol Simpan.")

            # === Validasi berhasil setelah simpan ===
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi')]"))
            )
            logging.info("🎉 Presensi berhasil!")

        except TimeoutException:
            logging.warning("⚠️ Gagal mengisi aktivitas atau tidak menemukan pesan konfirmasi. Mengambil tangkapan layar.")
            screenshot_name = f"artifacts/presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_name)
            logging.info(f"📸 Screenshot disimpan: {screenshot_name}")
            
    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan tak terduga: {e}")
        screenshot_name = f"artifacts/presensi_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_name)
        logging.info(f"📸 Screenshot error disimpan: {screenshot_name}")
    finally:
        if driver:
            driver.quit()
            logging.info("🚪 Keluar dari browser.")

# === Main ===
def main():
    tz = ZoneInfo("Asia/Jakarta")
    now = datetime.now(tz)
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({now.tzname()})")

    mode = os.environ.get("FORCE_MODE", "").strip()
    if not mode:
        if now.hour < 12:
            mode = "check_in"
        else:
            mode = "check_out"
    
    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")
        sys.exit(1)

    login_and_presensi(username, password, mode)

if __name__ == "__main__":
    main()
