import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ================== KONFIGURASI LOGGING ==================
log_filename = f"presensi_{time.strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ================== SETUP DRIVER ==================
def setup_driver():
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

# ================== PROSES PRESENSI ==================
def presensi(user: str, mode: str):
    logging.info(f"⏰ Mulai proses presensi untuk {user} (mode: {mode})...")

    username = os.environ.get(f"{user}_USERNAME")
    password = os.environ.get(f"{user}_PASSWORD")
    if not username or not password:
        logging.error(f"❌ Username/Password tidak ditemukan di secrets untuk {user}!")
        return False

    driver = setup_driver()
    if not driver:
        return False

    try:
        # 1. Buka halaman login
        url_login = "https://dani.perhutani.co.id/login"
        logging.info(f"🌐 [{user}] Membuka halaman login...")
        driver.get(url_login)

        # 2. Input username & password
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']"))
        ).send_keys(username)

        driver.find_element(By.XPATH, "//input[@placeholder='Password']").send_keys(password)

        driver.find_element(By.XPATH, "//button[contains(text(), 'Login') or @type='submit']").click()
        logging.info(f"🔐 [{user}] Login dikirim.")

        # 3. Hapus modal jika ada
        time.sleep(2)
        driver.execute_script("""
            let modals = document.querySelectorAll('.modal.show, #announcement');
            modals.forEach(m => m.remove());
        """)
        logging.info(f"❎ [{user}] Modal dihapus pakai JS.")

        # 4. Klik tombol presensi utama
        presensi_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/presensi')]"))
        )
        presensi_btn.click()
        logging.info(f"✅ [{user}] Klik: Tombol Presensi Utama.")

        # 5. Klik tombol popup presensi
        success = False
        for attempt in range(2):  # coba 2 kali
            try:
                popup_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Klik Disini Untuk Presensi')]"))
                )
                popup_btn.click()
                logging.info(f"🖱️ [{user}] Klik tombol popup presensi (percobaan {attempt+1}).")
                time.sleep(3)

                # cek status sesuai mode
                page_text = driver.page_source
                if mode == "check_in" and "Sudah Check In" in page_text:
                    logging.info(f"🎉 [{user}] Presensi check_in berhasil! Status: Sudah Check In")
                    success = True
                    break
                elif mode == "check_out" and "Sudah Check Out" in page_text:
                    logging.info(f"🎉 [{user}] Presensi check_out berhasil! Status: Sudah Check Out")
                    success = True
                    break
            except TimeoutException:
                logging.warning(f"⚠️ [{user}] Tombol popup presensi tidak ditemukan (percobaan {attempt+1}).")

        # 6. Jika gagal, laporkan status terakhir
        if not success:
            page_text = driver.page_source
            if "Sudah Check In" in page_text and mode == "check_out":
                logging.warning(f"⚠️ [{user}] Masih 'Sudah Check In', presensi check_out gagal.")
            elif "Sudah Check Out" in page_text and mode == "check_in":
                logging.warning(f"⚠️ [{user}] Sudah check_out sebelumnya, tidak bisa check_in.")
            else:
                logging.warning(f"⚠️ [{user}] Tidak menemukan indikator keberhasilan presensi ({mode}).")
        return success

    except Exception as e:
        logging.error(f"❌ [{user}] Terjadi kesalahan: {e}")
        return False
    finally:
        logging.info(f"🚪 [{user}] Keluar dari browser.")
        driver.quit()

# ================== MAIN ==================
if __name__ == "__main__":
    mode = os.environ.get("MODE", "check_in")  # default check_in
    users = ["USER1"]  # nanti bisa tambah USER2

    all_success = True
    for u in users:
        success = presensi(u, mode)
        if not success:
            all_success = False

    if not all_success:
        exit(1)
