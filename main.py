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
    logging.info("⚙️ Mengatur driver dengan profil persisten dan override lokasi...")
    try:
        # Bunuh proses Chrome lama
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()):
                proc.kill()

        chrome_options = webdriver.ChromeOptions()
        profile_path = os.path.join(os.getcwd(), "chrome-profile")
        os.makedirs(profile_path, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--profile-directory=Default")

        # Izin lokasi otomatis
        prefs = {"profile.default_content_setting_values.geolocation": 1}
        chrome_options.add_experimental_option("prefs", prefs)

        # Headless mode (hapus/comment untuk debug manual)
        chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(120)

        # Grant permission lokasi ke domain target
        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {
                "origin": "https://dani.perhutani.co.id",
                "permissions": ["geolocation"]
            }
        )

        # Inject API geolocation agar otomatis mengembalikan dummy lokasi
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                navigator.geolocation.getCurrentPosition = function(success, error){
                    success({ coords: { latitude: -7.250445, longitude: 112.768845, accuracy: 50 } });
                };
                navigator.geolocation.watchPosition = function(success, error){
                    success({ coords: { latitude: -7.250445, longitude: 112.768845, accuracy: 50 } });
                };
                """
            }
        )

        logging.info("✅ Driver siap dengan lokasi dummy dan override API.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# === Fungsi Debug ===
def save_debug(driver, name):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_path = f"artifacts/{name}_{ts}.html"
    screenshot_path = f"artifacts/{name}_{ts}.png"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    driver.save_screenshot(screenshot_path)
    logging.info(f"💾 Debug halaman disimpan: {html_path} & {screenshot_path}")

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
        logging.info("🔎 Cari field login...")
        user_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']")))
        pass_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
        user_field.send_keys(username)
        pass_field.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
        login_button.click()
        logging.info("✅ Klik tombol login.")

        # Tutup tutorial jika ada
        try:
            while True:
                next_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]"))
                )
                next_btn.click()
                time.sleep(1)
        except TimeoutException:
            logging.info("⚠️ Tidak ada tombol Next.")
        try:
            finish_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Finish')]"))
            )
            finish_btn.click()
        except TimeoutException:
            logging.info("⚠️ Tidak ada tombol Finish.")

        # Buka halaman presensi
        presensi_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]")))
        driver.execute_script("arguments[0].click();", presensi_menu)
        logging.info("✅ Menu presensi diklik.")
        time.sleep(5)

        # Klik tombol utama presensi
        presensi_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Klik Disini')]")))
        driver.execute_script("arguments[0].click();", presensi_btn)
        logging.info("✅ Tombol presensi utama diklik.")
        time.sleep(3)

        # Tunggu koordinat terisi
        for i in range(3):
            lat = driver.execute_script("return document.getElementById('result_lat')?.value;")
            lon = driver.execute_script("return document.getElementById('result_long')?.value;")
            logging.info(f"📍 Cek koordinat ke-{i+1}: lat={lat}, lon={lon}")
            if lat and lon:
                break
            time.sleep(3)

        # Klik tombol presensi di popup
        popup_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik Disini Untuk Presensi')]")))
        driver.execute_script("arguments[0].click();", popup_btn)
        logging.info("✅ Tombol presensi popup diklik.")
        time.sleep(5)

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
        logging.error("❌ Username/password tidak ditemukan!")
        sys.exit(1)

    mode = os.environ.get("FORCE_MODE", "check_in" if now.hour < 12 else "check_out")

    for attempt in range(1, 4):
        logging.info(f"🔄 Percobaan ke-{attempt}...")
        if attempt_presensi(username, password, mode):
            logging.info("✅ Presensi berhasil.")
            break
        else:
            logging.warning(f"⚠️ Percobaan ke-{attempt} gagal, coba lagi dalam 10 detik...")
            time.sleep(10)
    else:
        logging.error("❌ Semua percobaan gagal!")

if __name__ == "__main__":
    main()
