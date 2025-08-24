import os
import sys
import time
import logging
from tempfile import mkdtemp
from datetime import datetime
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException
)

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
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()

        # Nonaktifkan headless untuk debug, aktifkan jika sudah stabil
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")

        # Direktori unik untuk menghindari konflik
        user_data_dir = mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# === Fungsi Presensi ===
def login_and_presensi(username, password, mode="check_in"):
    url_login = "https://dani.perhutani.co.id/login"
    driver = setup_driver()
    if not driver:
        return

    try:
        driver.get(url_login)
        wait = WebDriverWait(driver, 30)

        # Hapus modal popup announcement jika ada
        try:
            modal = driver.find_element(By.ID, "announcement")
            if modal.is_displayed():
                driver.execute_script("arguments[0].remove();", modal)
                logging.info("❎ Modal login dihapus pakai JS.")
        except Exception:
            pass

        # === Input Username & Password ===
        logging.info("🔎 Cari field login...")
        username_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='NPK' or contains(@name,'username') or contains(@id,'username')]")
        ))
        password_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Password' or @type='password']")
        ))

        username_input.send_keys(username)
        password_input.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Login') or contains(text(),'Masuk') or @type='submit']")
        ))
        login_button.click()
        logging.info("✅ Klik tombol login.")

        # === Tutup popup Next / Finish jika ada ===
        try:
            next_count = 0
            while True:
                try:
                    next_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'Selanjutnya')]"))
                    )
                    next_button.click()
                    next_count += 1
                    logging.info(f"⏭️ Klik Next ({next_count})")
                    time.sleep(1)
                except TimeoutException:
                    break
            try:
                finish_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]"))
                )
                finish_button.click()
                logging.info("🏁 Klik Finish.")
            except TimeoutException:
                logging.info("⚠️ Tidak menemukan tombol Finish, lanjut.")
        except Exception as e:
            logging.warning(f"⚠️ Popup tidak tertutup sempurna: {e}")

        # === Masuk ke halaman presensi ===
        presensi_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]"))
        )
        try:
            presensi_button.click()
            logging.info("✅ Klik tombol menu Presensi.")
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", presensi_button)
            logging.info("✅ Klik tombol menu Presensi dengan JS.")

        logging.info("⏳ Menunggu halaman presensi terbuka sepenuhnya...")
        time.sleep(8)

        # === Cari dan klik tombol oranye di halaman utama ===
        orange_button = None
        for attempt in range(3):
            try:
                orange_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[contains(@class,'text-center') and (contains(.,'Klik Disini Untuk Presensi') or .//i or .//svg)]"
                    ))
                )
                logging.info(f"✅ Tombol presensi ditemukan (percobaan {attempt+1}).")
                break
            except TimeoutException:
                logging.warning(f"⏳ Tombol presensi belum muncul (percobaan {attempt+1}). Menunggu ulang...")
                time.sleep(5)

        if orange_button:
            driver.execute_script("arguments[0].scrollIntoView(true);", orange_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", orange_button)
            logging.info("✅ Klik tombol presensi oranye di halaman utama.")
        else:
            logging.error("❌ Tombol presensi oranye tetap tidak ditemukan setelah 3 kali percobaan.")
            screenshot_name = f"artifacts/presensi_button_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_name)
            logging.info(f"📸 Screenshot disimpan: {screenshot_name}")
            driver.quit()
            return

        time.sleep(3)

        # === Klik tombol presensi di popup ===
        try:
            popup_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(),'Klik Disini Untuk Presensi')]"
                ))
            )
            driver.execute_script("arguments[0].click();", popup_button)
            logging.info("✅ Klik tombol presensi pada popup.")
        except TimeoutException:
            logging.error("❌ Tombol popup presensi tidak ditemukan.")
            screenshot_name = f"artifacts/presensi_popup_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_name)
            logging.info(f"📸 Screenshot disimpan: {screenshot_name}")
            driver.quit()
            return

        # === Validasi presensi berhasil ===
        try:
            success_message = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi')]"
                ))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            screenshot_name = f"artifacts/presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(screenshot_name)
            logging.info(f"📸 Screenshot disimpan: {screenshot_name}")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        screenshot_name = f"artifacts/presensi_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_name)
        logging.info(f"📸 Screenshot error disimpan: {screenshot_name}")
    finally:
        driver.quit()
        logging.info("🚪 Keluar dari browser.")

# === Main ===
def main():
    tz = ZoneInfo("Asia/Jakarta")
    now = datetime.now(tz)
    logging.info("⏰ Mulai proses presensi...")

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
