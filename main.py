import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def get_credentials():
    """Ambil username & password dari GitHub Secrets"""
    username = os.getenv("USER1") or os.getenv("USER1_USERNAME")
    password = os.getenv("PASS1") or os.getenv("USER1_PASSWORD")

    if not username or not password:
        logging.error("❌ Username/Password tidak ditemukan di secrets!")
        raise SystemExit(1)

    logging.info("✅ Kredensial ditemukan. Mencoba login sebagai: ***")
    return username, password

def run_presensi():
    username, password = get_credentials()

    logging.info("⚙️ Mengatur driver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get("https://dani.perhutani.co.id/")

        # Login step
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "npk"))
        ).send_keys(username)

        driver.find_element(By.NAME, "password").send_keys(password)

        btn_login = driver.find_element(By.XPATH, "//button[@type='submit']")
        btn_login.click()
        logging.info("✅ Klik tombol login.")

        # Tunggu popup / announcement
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        time.sleep(5)
        try:
            driver.execute_script("""
                let modal = document.querySelector('#announcement');
                if (modal) { modal.remove(); }
            """)
            logging.info("❎ Modal dihapus pakai JS.")
        except Exception:
            logging.info("⚠️ Tidak menemukan modal.")

        # Tunggu tombol presensi
        logging.info("⏳ Menunggu tombol presensi utama...")
        btn_presensi = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'/presensi')]"))
        )
        btn_presensi.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")

        # Konfirmasi presensi
        try:
            notif = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "swal2-title"))
            )
            logging.info(f"✅ Presensi berhasil: {notif.text}")
        except TimeoutException:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            filename = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(filename)
            logging.info(f"📸 Screenshot disimpan: {filename}")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        logging.info("🚪 Keluar dari browser.")
        driver.quit()

if __name__ == "__main__":
    run_presensi()
