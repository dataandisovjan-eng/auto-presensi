import sys
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Konfigurasi logging
log_filename = "presensi.log"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])

def setup_driver():
    """Mengatur dan menginisialisasi WebDriver."""
    logging.info("⚙️ Mengatur driver...")
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")

        chrome_path = os.environ.get("CHROMEDRIVER_PATH", "chromedriver")
        service = ChromeService(executable_path=chrome_path)

        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(90)
        logging.info("✅ Driver siap.")
        return driver
    except WebDriverException as e:
        logging.error(f"❌ Gagal mengatur driver: {e}")
        return None

def debug_list_inputs(driver, iframe_index=None):
    """Log semua input di halaman saat ini."""
    inputs = driver.find_elements(By.TAG_NAME, "input")
    if iframe_index is not None:
        logging.info(f"🔎 Debug input di dalam iframe[{iframe_index}] (total {len(inputs)} elemen)")
    else:
        logging.info(f"🔎 Debug input di halaman utama (total {len(inputs)} elemen)")
    for inp in inputs:
        logging.info(
            f"    <input id='{inp.get_attribute('id')}' "
            f"name='{inp.get_attribute('name')}' "
            f"placeholder='{inp.get_attribute('placeholder')}' "
            f"type='{inp.get_attribute('type')}' "
            f"class='{inp.get_attribute('class')}' />"
        )

def find_input(driver, wait, labels, input_type="text"):
    """
    Mencari input berdasarkan label/placeholder/nama.
    labels = daftar keyword untuk pencarian (contoh: ["username","nip","email"])
    input_type = 'text' atau 'password'
    """
    # 1. Coba dengan XPath umum
    xpath_conditions = [
        f"//input[@id='{lbl}']" for lbl in labels
    ] + [
        f"//input[@name='{lbl}']" for lbl in labels
    ] + [
        f"//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{lbl}')]"
        for lbl in labels
    ]

    # Tambahkan fallback berdasarkan type
    if input_type == "text":
        xpath_conditions.append("//input[@type='text']")
    elif input_type == "password":
        xpath_conditions.append("//input[@type='password']")

    # Cari di halaman utama
    debug_list_inputs(driver)
    for xp in xpath_conditions:
        try:
            return wait.until(EC.presence_of_element_located((By.XPATH, xp)))
        except TimeoutException:
            continue

    # Fallback: manual cek atribut input
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        ph = (inp.get_attribute("placeholder") or "").lower()
        nm = (inp.get_attribute("name") or "").lower()
        idv = (inp.get_attribute("id") or "").lower()
        if any(lbl in ph or lbl in nm or lbl in idv for lbl in labels):
            return inp

    # Cari di semua iframe
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    logging.info(f"🔎 Ditemukan {len(iframes)} iframe. Coba cek satu-satu...")
    for idx, iframe in enumerate(iframes):
        driver.switch_to.frame(iframe)
        debug_list_inputs(driver, idx)

        for xp in xpath_conditions:
            try:
                return wait.until(EC.presence_of_element_located((By.XPATH, xp)))
            except TimeoutException:
                continue

        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            ph = (inp.get_attribute("placeholder") or "").lower()
            nm = (inp.get_attribute("name") or "").lower()
            idv = (inp.get_attribute("id") or "").lower()
            if any(lbl in ph or lbl in nm or lbl in idv for lbl in labels):
                return inp

        driver.switch_to.default_content()

    raise TimeoutException(f"❌ Tidak menemukan field dengan keyword {labels}.")

def main():
    """Fungsi utama untuk menjalankan skrip presensi."""
    username = os.environ.get('USER1_USERNAME')
    password = os.environ.get('USER1_PASSWORD')
    url_login = "https://dani.perhutani.co.id/login"

    if not username or not password:
        logging.error("❌ Kredensial tidak ditemukan. Pastikan 'USER1_USERNAME' dan 'USER1_PASSWORD' sudah diatur.")
        return

    logging.info(f"✅ Kredensial ditemukan. Mencoba login sebagai: {username}")

    driver = setup_driver()
    if not driver:
        return

    try:
        logging.info("🌐 Buka halaman login...")
        driver.get(url_login)

        wait = WebDriverWait(driver, 30)

        # Cari field username
        logging.info("🔎 Cari field username...")
        username_input = find_input(driver, wait, ["username","nip","email","user"], "text")
        username_input.send_keys(username)
        logging.info("✅ Field username terisi.")

        # Cari field password
        logging.info("🔎 Cari field password...")
        password_input = find_input(driver, wait, ["password","kata sandi","sandi","pass"], "password")
        password_input.send_keys(password)
        logging.info("✅ Field password terisi.")

        # Cari tombol login
        logging.info("🔎 Mencari tombol login...")
        try:
            login_button = wait.until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login') or " +
                    "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'masuk') or " +
                    "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in') or " +
                    "@type='submit']"
                ))
            )
            login_button.click()
            logging.info("✅ Klik tombol login.")
        except TimeoutException:
            raise TimeoutException("❌ Tombol login tidak ditemukan.")

        driver.switch_to.default_content()
        logging.info("✅ Kembali ke konten utama.")

        # Pop-up jika ada
        logging.info("🔎 Mencari pop-up...")
        try:
            wait_for_popup = WebDriverWait(driver, 15)
            for _ in range(5):
                try:
                    next_button = wait_for_popup.until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Next') or contains(text(),'next')]"))
                    )
                    next_button.click()
                    logging.info("⏭️ Klik Next")
                    time.sleep(1)
                except TimeoutException:
                    break

            try:
                finish_button = wait_for_popup.until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Finish') or contains(text(),'Selesai') or contains(text(),'finish')]"))
                )
                finish_button.click()
                logging.info("🏁 Klik Finish/Selesai.")
            except TimeoutException:
                pass
        except Exception as e:
            logging.warning(f"Gagal menutup pop-up: {e}")

        # Tombol presensi
        logging.info("⏳ Menunggu tombol presensi utama...")
        presensi_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn-presensi')]"))
        )
        presensi_button.click()
        logging.info("✅ Klik Tombol Presensi Utama.")
        time.sleep(5)

        # Konfirmasi presensi
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH,
                    "//*[contains(text(),'Presensi berhasil') or " +
                    "contains(text(),'Anda telah melakukan presensi')]"))
            )
            logging.info("🎉 Presensi berhasil!")
        except TimeoutException:
            logging.warning("⚠️ Tidak ada pesan konfirmasi presensi.")

    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        if driver:
            logging.info("🚪 Keluar dari browser.")
            try:
                driver.close()
            except:
                pass
            driver.quit()

if __name__ == "__main__":
    main()
