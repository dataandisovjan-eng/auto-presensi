import os
import sys
import time
import psutil
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# === Konfigurasi Logging ===
os.makedirs("artifacts", exist_ok=True)
log_file = f"artifacts/presensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# === Setup Driver ===
def setup_driver():
    logging.info("⚙️ Menyiapkan driver dengan geolocation override...")
    try:
        # Tutup Chrome/Chromedriver yang masih aktif
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                proc.kill()

        chrome_options = webdriver.ChromeOptions()
        profile_path = os.path.join(os.getcwd(), "chrome-profile")
        os.makedirs(profile_path, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # Headless mode (hapus/comment baris ini untuk debug manual)
        chrome_options.add_argument("--headless=new")

        # Izin otomatis geolocation
        prefs = {"profile.default_content_setting_values.geolocation": 1}
        chrome_options.add_experimental_option("prefs", prefs)

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)

        # Grant permission ke domain target
        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {
                "origin": "https://dani.perhutani.co.id",
                "permissions": ["geolocation"]
            }
        )

        # Dummy koordinat dari environment
        LAT = float(os.environ.get("LAT", "-7.250445"))
        LON = float(os.environ.get("LON", "112.768845"))

        # Inject API geolocation override
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": f"""
                navigator.geolocation.getCurrentPosition = function(success, error){{
                    success({{ coords: {{ latitude: {LAT}, longitude: {LON}, accuracy: 50 }} }});
                }};
                navigator.geolocation.watchPosition = function(success, error){{
                    success({{ coords: {{ latitude: {LAT}, longitude: {LON}, accuracy: 50 }} }});
                }};
                """
            }
        )

        logging.info(f"✅ Driver siap dengan lokasi LAT={LAT}, LON={LON}.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal menyiapkan driver: {e}")
        return None

# === Fungsi Debug ===
def save_debug(driver, name):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_path = f"artifacts/{name}_{ts}.html"
    screenshot_path = f"artifacts/{name}_{ts}.png"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    driver.save_screenshot(screenshot_path)
    logging.info(f"💾 Debug disimpan: {html_path} & {screenshot_path}")

# === Proses Presensi ===
def attempt_presensi(username, password, mode):
    url = "https://dani.perhutani.co.id/login"
    driver = setup_driver()
    if not driver:
        return False

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 30)

        # Login
        logging.info("🔎 Mengisi field login...")
        user_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']")))
        pass_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
        user_field.send_keys(username)
        pass_field.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
        login_button.click()
        logging.info("✅ Login berhasil diklik.")

        # Tutup tutorial jika muncul
        try:
            while True:
                next_btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]"))
                )
                next_btn.click()
                time.sleep(1)
        except TimeoutException:
            logging.info("⚠️ Tidak ada tombol Next.")
        try:
            finish_btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Finish')]"))
            )
            finish_btn.click()
        except TimeoutException:
            logging.info("⚠️ Tidak ada tombol Finish.")

        # Klik menu Presensi
        presensi_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]")))
        driver.execute_script("arguments[0].click();", presensi_menu)
        logging.info("✅ Menu Presensi diklik.")
        time.sleep(5)

        # Cari tombol "Klik Disini"
        logging.info("🔍 Mencari tombol presensi utama...")
        xpath_button = (
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'klik disini')] "
            "| //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'klik disini')] "
            "| //div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'klik disini')]"
        )

        for attempt in range(5):
            try:
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath_button)))
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                btn.click()
                logging.info("✅ Tombol presensi utama diklik.")
                break
            except TimeoutException:
                logging.warning(f"⏳ Tombol presensi belum muncul, retry {attempt+1}/5...")
                time.sleep(3)
        else:
            logging.error("❌ Tombol presensi utama tidak ditemukan.")
            save_debug(driver, "presensi_button_missing")
            return False

        # Tunggu popup presensi
        logging.info("⏳ Menunggu popup presensi terbuka...")
        time.sleep(5)

        # Klik tombol presensi di popup
        logging.info("🔍 Mencari tombol presensi di popup...")
        for attempt in range(5):
            try:
                popup_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath_button))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", popup_btn)
                time.sleep(1)
                popup_btn.click()
                logging.info("✅ Tombol presensi popup diklik.")
                break
            except TimeoutException:
                logging.warning(f"⏳ Tombol popup belum muncul, retry {attempt+1}/5...")
                time.sleep(3)
        else:
            logging.error("❌ Tombol popup presensi tidak ditemukan.")
            save_debug(driver, "presensi_popup_missing")
            return False

        # Verifikasi
        try:
            wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Presensi berhasil')]")))
            logging.info("🎉 Presensi berhasil!")
            return True
        except TimeoutException:
            logging.warning("⚠️ Tidak ada konfirmasi presensi.")
            save_debug(driver, "presensi_notif_missing")
            return False

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        save_debug(driver, "presensi_error")
        return False
    finally:
        driver.quit()
        logging.info("🚪 Browser ditutup.")

# === Main ===
def main():
    tz = ZoneInfo("Asia/Jakarta")
    now = datetime.now(tz)
    logging.info("⏰ Mulai proses presensi...")

    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")
    if not username or not password:
        logging.error("❌ Username/password tidak ditemukan di environment variables!")
        sys.exit(1)

    mode = os.environ.get("FORCE_MODE", "check_in" if now.hour < 12 else "check_out")

    for attempt in range(1, 4):
        logging.info(f"🔄 Percobaan ke-{attempt}...")
        if attempt_presensi(username, password, mode):
            logging.info("✅ Presensi berhasil dilakukan.")
            break
        else:
            logging.warning(f"⚠️ Percobaan ke-{attempt} gagal, menunggu 10 detik...")
            time.sleep(10)
    else:
        logging.error("❌ Semua percobaan presensi gagal!")

if __name__ == "__main__":
    main()
