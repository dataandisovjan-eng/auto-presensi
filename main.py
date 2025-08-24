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

# === Lokasi Dummy ===
LAT = float(os.environ.get("LAT", "-7.177347"))
LON = float(os.environ.get("LON", "111.874487"))

# === Setup Driver ===
def setup_driver():
    logging.info("⚙️ Mengatur driver dengan profil persisten dan override lokasi...")
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                proc.kill()

        chrome_options = webdriver.ChromeOptions()
        profile_path = os.path.join(os.getcwd(), "chrome-profile")
        os.makedirs(profile_path, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        prefs = {"profile.default_content_setting_values.geolocation": 1}
        chrome_options.add_experimental_option("prefs", prefs)

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)

        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {"origin": "https://dani.perhutani.co.id", "permissions": ["geolocation"]}
        )

        geo_override = f"""
        navigator.geolocation.getCurrentPosition = function(success, error){{
            success({{ coords: {{ latitude: {LAT}, longitude: {LON}, accuracy: 50 }} }});
        }};
        navigator.geolocation.watchPosition = function(success, error){{
            success({{ coords: {{ latitude: {LAT}, longitude: {LON}, accuracy: 50 }} }});
        }};
        """
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": geo_override})

        logging.info(f"✅ Driver siap dengan lokasi dummy lat={LAT}, lon={LON}")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# === Debug Helper ===
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
        user_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']")))
        pass_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
        user_field.send_keys(username)
        pass_field.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
        login_button.click()
        logging.info("✅ Login berhasil.")

        # Tutup tutorial kalau muncul
        try:
            while True:
                next_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]"))
                )
                next_btn.click()
                time.sleep(1)
        except TimeoutException:
            pass
        try:
            finish_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Finish')]"))
            )
            finish_btn.click()
        except TimeoutException:
            pass

        # Masuk ke menu presensi
        presensi_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]")))
        driver.execute_script("arguments[0].click();", presensi_menu)
        time.sleep(5)

        # Klik tombol utama presensi
        presensi_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Klik Disini')]")))
        driver.execute_script("arguments[0].click();", presensi_btn)
        time.sleep(3)

        # Tunggu koordinat → jika tetap kosong, isi manual
        lat = lon = None
        for i in range(10):
            lat = driver.execute_script("return document.getElementById('result_lat')?.value;")
            lon = driver.execute_script("return document.getElementById('result_long')?.value;")
            logging.info(f"📍 Cek koordinat ke-{i+1}: lat={lat}, lon={lon}")
            if lat and lon:
                break
            time.sleep(3)

        if not lat or not lon:
            logging.warning("⚠️ Koordinat tidak terisi, paksa isi manual.")
            driver.execute_script(f"""
                document.getElementById('result_lat').value = {LAT};
                document.getElementById('result_long').value = {LON};
            """)
            lat = driver.execute_script("return document.getElementById('result_lat').value;")
            lon = driver.execute_script("return document.getElementById('result_long').value;")
            logging.info(f"📍 Koordinat dipaksa: lat={lat}, lon={lon}")

        # Klik tombol popup presensi
        popup_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Klik Disini Untuk Presensi')]"))
        )
        driver.execute_script("arguments[0].click();", popup_btn)
        logging.info("✅ Tombol popup presensi diklik.")
        time.sleep(5)

        # Verifikasi berhasil
        try:
            wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Presensi berhasil')]")))
            logging.info("🎉 Presensi berhasil!")
            return True
        except TimeoutException:
            logging.warning("⚠️ Tidak ada notifikasi presensi.")
            save_debug(driver, "presensi_notif_missing")
            return False
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        save_debug(driver, "presensi_error")
        return False
    finally:
        driver.quit()

# === Main ===
def main():
    tz = ZoneInfo("Asia/Jakarta")
    now = datetime.now(tz)
    logging.info("⏰ Mulai proses presensi otomatis...")

    username = os.environ.get("USER1_USERNAME")
    password = os.environ.get("USER1_PASSWORD")
    if not username or not password:
        logging.error("❌ Username/password tidak ditemukan di environment!")
        sys.exit(1)

    mode = os.environ.get("FORCE_MODE", "check_in" if now.hour < 12 else "check_out")

    for attempt in range(1, 4):
        logging.info(f"🔄 Percobaan ke-{attempt}...")
        if attempt_presensi(username, password, mode):
            logging.info("✅ Presensi selesai.")
            break
        else:
            logging.warning(f"⚠️ Percobaan {attempt} gagal, retry 10 detik...")
            time.sleep(10)
    else:
        logging.error("❌ Semua percobaan gagal.")

if __name__ == "__main__":
    main()
