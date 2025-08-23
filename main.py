import os
import sys
import time
import shutil
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# ========== SETUP LOGGING ==========
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"run_log_{timestamp}.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=os.path.join("logs", log_filename),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# ========== SETUP ARTIFACTS FOLDER ==========
ARTIFACT_DIR = "artifacts"
SCREENSHOT_DIR = "screenshots"
os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def save_screenshot(driver, name: str):
    """Simpan screenshot ke folder screenshots/"""
    path = os.path.join(SCREENSHOT_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    driver.save_screenshot(path)
    logging.info(f"📸 Screenshot disimpan: {path}")
    return path

def move_to_artifacts():
    """Pindahkan semua logs & screenshots ke artifacts/"""
    for folder in [SCREENSHOT_DIR, "logs"]:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                src = os.path.join(folder, f)
                dst = os.path.join(ARTIFACT_DIR, f)
                try:
                    shutil.copy(src, dst)
                except Exception as e:
                    logging.warning(f"⚠️ Gagal copy {src} → {dst}: {e}")
    logging.info("📦 Semua hasil dipindahkan ke artifacts/")

# ========== START SELENIUM ==========
def run_presensi(username, password):
    logging.info("✅ Kredensial ditemukan. Mencoba login...")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)

    try:
        # Buka login
        logging.info("🌐 Buka halaman login...")
        driver.get("https://dani.perhutani.co.id/login")

        # Isi username & password
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(username)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)

        # Klik login
        login_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        login_btn.click()
        logging.info("✅ Klik tombol login.")

        # Tunggu masuk dashboard
        time.sleep(5)

        # Tutup popup (kalau ada)
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        try:
            finish_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Finish')]"))
            )
            finish_btn.click()
            logging.info("✅ Klik tombol Finish.")
        except TimeoutException:
            logging.info("⚠️ Tidak menemukan tombol Finish, lanjut.")
            # Hapus modal dengan JS kalau menghalangi
            try:
                driver.execute_script("document.querySelectorAll('.modal.show').forEach(m => m.remove());")
                logging.info("❎ Modal dihapus pakai JS.")
            except Exception:
                pass

        # Klik tombol presensi utama
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'presensi')]"))
        )
        presensi_btn.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")

        # Cari notifikasi konfirmasi presensi
        notif = None
        possible_selectors = [
            ".swal2-popup", ".swal2-container",  # SweetAlert2
            ".toast-message", ".toast",          # Toast notification
            ".alert", ".alert-success"           # Bootstrap alerts
        ]
        for sel in possible_selectors:
            try:
                notif = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                break
            except TimeoutException:
                continue

        if notif:
            logging.info(f"✅ Notifikasi presensi ditemukan: {notif.text}")
        else:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            save_screenshot(driver, "presensi_notif_missing")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
        save_screenshot(driver, "error")
    finally:
        driver.quit()
        logging.info("🚪 Keluar dari browser.")
        move_to_artifacts()

# ========== MAIN ==========
if __name__ == "__main__":
    USERNAME = os.getenv("USER1")
    PASSWORD = os.getenv("PASS1")
    if not USERNAME or not PASSWORD:
        logging.error("❌ Username/Password tidak ditemukan di secrets!")
        sys.exit(1)

    run_presensi(USERNAME, PASSWORD)
