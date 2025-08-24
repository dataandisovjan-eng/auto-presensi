import os
import sys
import time
import tempfile
import psutil
import logging
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

# === Logging ===
os.makedirs("artifacts", exist_ok=True)
log_filename = f"artifacts/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# === Setup Driver ===
def setup_driver():
    logging.info("⚙️ Mengatur driver dengan izin lokasi...")
    try:
        # Bunuh semua proses Chrome/Chromedriver yang tertinggal
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                    proc.kill()
            except Exception:
                pass

        chrome_options = webdriver.ChromeOptions()
        unique_profile = tempfile.mkdtemp(prefix="profile_")
        chrome_options.add_argument(f"--user-data-dir={unique_profile}")
        chrome_options.add_argument(f"--profile-directory=Profile_{int(time.time())}")

        # Aktifkan izin lokasi
        prefs = {
            "profile.default_content_setting_values.geolocation": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Opsi tambahan
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--headless=new")

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# === Simpan Debug HTML & Screenshot ===
def save_debug(driver, name):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_path = f"artifacts/{name}_{timestamp}.html"
    screenshot_path = f"artifacts/{name}_{timestamp}.png"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    driver.save_screenshot(screenshot_path)
    logging.info(f"💾 Debug halaman disimpan: {html_path} & {screenshot_path}")

# === Fungsi Presensi ===
def attempt_presensi(username, password, mode):
    url_login = "https://dani.perhutani.co.id/login"
    driver = setup_driver()
    if not driver:
        return False

    try:
        driver.get(url_login)
        wait = WebDriverWait(driver, 30)

        # Tutup modal login jika ada
        try:
            modal = driver.find_element(By.ID, "announcement")
            if modal.is_displayed():
                driver.execute_script("arguments[0].remove();", modal)
                logging.info("❎ Modal login dihapus.")
        except Exception:
            pass

        # === Login ===
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

        # Tutup popup intro jika ada
        try:
            while True:
                try:
                    next_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//*[contains(text(),'Next') or contains(text(),'Selanjutnya')]")
                        )
                    )
                    next_button.click()
                    logging.info("⏭️ Klik Next.")
                    time.sleep(1)
                except TimeoutException:
                    break
            try:
                finish_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai')]")
                    )
                )
                finish_button.click()
                logging.info("🏁 Klik Finish.")
            except TimeoutException:
                logging.info("⚠️ Tidak menemukan tombol Finish.")
        except Exception as e:
            logging.warning(f"⚠️ Popup intro tidak tertutup: {e}")

        # === Masuk ke halaman presensi ===
        presensi_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]"))
        )
        driver.execute_script("arguments[0].click();", presensi_button)
        logging.info("✅ Klik menu Presensi.")

        logging.info("⏳ Menunggu halaman presensi terbuka...")
        time.sleep(8)

        # === Klik tombol presensi utama ===
        logging.info("🔍 Mencari tombol presensi utama...")
        try:
            orange_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[contains(@class,'text-center') and (contains(text(),'Klik Disini') or contains(.,'Presensi'))]"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", orange_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", orange_button)
            logging.info("✅ Klik tombol presensi utama.")
        except TimeoutException:
            logging.error("❌ Tombol presensi utama tidak ditemukan.")
            save_debug(driver, "presensi_button_missing")
            return False

        time.sleep(3)

        # === Klik tombol popup presensi ===
        logging.info("🔍 Mencari tombol presensi di popup...")
        try:
            time.sleep(3)  # Tambahan delay render popup
            try:
                driver.find_element(By.XPATH, "//*[contains(text(),'Belum Mengijinkan')]")
                logging.warning("⚠️ Pesan lokasi muncul, abaikan dan lanjut.")
            except:
                logging.info("✅ Tidak ada pesan lokasi, lanjut.")

            popup_button = WebDriverWait(driver, 25).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(.,'Klik Disini Untuk Presensi')]"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", popup_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", popup_button)
            logging.info("✅ Klik tombol presensi di popup berhasil.")
            time.sleep(5)
        except TimeoutException:
            logging.error("❌ Tombol popup presensi tidak ditemukan.")
            save_debug(driver, "presensi_popup_missing")
            return False

        # === Verifikasi berhasil ===
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    "//*[contains(text(),'Presensi berhasil') or contains(text(),'Anda telah melakukan presensi')]"
                ))
            )
            logging.info("🎉 Presensi berhasil!")
            return True
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            save_debug(driver, "presensi_notif_missing")
            return False

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        save_debug(driver, "presensi_error")
        return False
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
        mode = "check_in" if now.hour < 12 else "check_out"

    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets untuk USER1!")
        sys.exit(1)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        logging.info(f"🔄 Percobaan presensi ke-{attempt}...")
        if attempt_presensi(username, password, mode):
            logging.info("✅ Presensi selesai dengan sukses.")
            break
        else:
            logging.warning(f"⚠️ Percobaan ke-{attempt} gagal, menunggu 10 detik sebelum mencoba lagi...")
            time.sleep(10)
    else:
        logging.error("❌ Semua percobaan presensi gagal!")

if __name__ == "__main__":
    main()
