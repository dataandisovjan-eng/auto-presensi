import os
import time
import argparse
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def get_credentials():
    """Ambil username dan password dari GitHub Secrets"""
    creds = {}
    possible_keys = [
        ("USER1", "PASS1"),
        ("USER1_USERNAME", "USER1_PASSWORD"),
        ("ANDI_USERNAME", "ANDI_PASSWORD"),
    ]

    for u_key, p_key in possible_keys:
        user = os.getenv(u_key)
        pw = os.getenv(p_key)
        if user and pw:
            creds["username"] = user
            creds["password"] = pw
            logging.info("✅ Kredensial ditemukan. Mencoba login sebagai: ***")
            return creds

    logging.error("❌ Username/Password tidak ditemukan di secrets!")
    exit(1)

def setup_driver():
    """Setup Selenium driver"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    return driver

def run_presensi(mode="check_in"):
    """Fungsi utama presensi"""
    creds = get_credentials()
    driver = setup_driver()

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get("https://dani.perhutani.co.id/auth/login")

        # Isi username
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        ).send_keys(creds["username"])

        # Isi password
        driver.find_element(By.ID, "password").send_keys(creds["password"])

        # Klik login
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        logging.info("✅ Klik tombol login.")

        # Tunggu halaman utama
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Tutup popup jika ada
        logging.info("🔎 Mencari pop-up untuk ditutup...")
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "announcement"))
            )
            driver.execute_script("""
                let modal = document.getElementById('announcement');
                if(modal) { modal.remove(); }
            """)
            logging.info("❎ Modal dihapus pakai JS.")
        except:
            logging.info("⚠️ Tidak menemukan modal popup, lanjut.")

        # Klik tombol presensi utama
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='presensi']"))
        )
        presensi_btn.click()
        logging.info("✅ Klik: Tombol Presensi Utama.")

        # Konfirmasi
        try:
            notif = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "swal2-title"))
            )
            logging.info(f"📢 Notifikasi: {notif.text}")
        except:
            logging.warning("⚠️ Pesan konfirmasi presensi tidak ditemukan.")
            filename = f"presensi_notif_missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            driver.save_screenshot(filename)
            logging.info(f"📸 Screenshot disimpan: {filename}")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        driver.quit()
        logging.info("🚪 Keluar dari browser.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["check_in", "check_out"], default="check_in")
    args = parser.parse_args()

    logging.info(f"⚡ Mode presensi dipilih: {args.mode}")
    run_presensi(mode=args.mode)

if __name__ == "__main__":
    main()
