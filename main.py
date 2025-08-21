import os
import time
import logging
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("presensi.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# daftar user (ambil dari secrets di workflow)
USERS = [
    {"name": "Pak Budi", "secret_user": "USER1", "secret_pass": "PASS1"},
    {"name": "Bu Sari", "secret_user": "USER2", "secret_pass": "PASS2"},
]

# jadwal presensi
JADWAL = {
    "check_in": "05:30",
    "check_out": "16:05",
}

URL_LOGIN = "https://dani.perhutani.co.id/login"

def now_jkt():
    tz = pytz.timezone("Asia/Jakarta")
    return datetime.now(tz)

def wait_and_click(driver, by, selector, timeout=15):
    """Tunggu elemen sampai clickable lalu klik"""
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    time.sleep(0.3)
    el.click()
    return el

def safe_find_input(driver, name="npk", timeout=15):
    """Cari input login, pastikan visible & clickable"""
    selectors = [
        (By.NAME, name),
        (By.ID, name),
        (By.CSS_SELECTOR, "input[type='text']"),
        (By.TAG_NAME, "input"),
    ]
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, sel))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.3)
            return el
        except:
            continue
    raise Exception("❌ Tidak bisa menemukan field login NPK")

def login(driver, user):
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])

    logging.info(f"[{user['name']}] 🔐 Proses login...")

    # isi username
    username_field = safe_find_input(driver, "npk")
    username_field.clear()
    username_field.send_keys(username)

    # isi password
    password_field = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.NAME, "password"))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", password_field)
    time.sleep(0.3)
    password_field.clear()
    password_field.send_keys(password)
    password_field.send_keys(Keys.RETURN)

    logging.info(f"[{user['name']}] ✅ Login form submitted")

def handle_popup(driver, user):
    """Tutup popup 'Next' sampai selesai"""
    while True:
        try:
            next_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Next') or contains(.,'next')]"))
            )
            next_btn.click()
            logging.info(f"[{user['name']}] ⏭️ Klik Next popup")
            time.sleep(1)
        except:
            try:
                finish_btn = driver.find_element(By.XPATH, "//button[contains(.,'Finish') or contains(.,'finish')]")
                finish_btn.click()
                logging.info(f"[{user['name']}] 🏁 Klik Finish popup")
                time.sleep(1)
            except:
                break

def lakukan_presensi(driver, user, mode="check_in"):
    """Klik tombol presensi"""
    try:
        handle_popup(driver, user)

        # tombol utama
        main_btn = wait_and_click(driver, By.XPATH, "//button[contains(.,'klik disini untuk presensi')]")
        logging.info(f"[{user['name']}] 🟠 Klik tombol utama presensi")

        time.sleep(2)

        # popup konfirmasi presensi
        confirm_btn = wait_and_click(driver, By.XPATH, "//button[contains(.,'klik disini untuk presensi')]")
        logging.info(f"[{user['name']}] 🟠 Klik tombol konfirmasi presensi")

        time.sleep(3)
        driver.save_screenshot(f"{user['name']}_{mode}.png")
        logging.info(f"[{user['name']}] ✅ Presensi {mode} selesai")
    except Exception as e:
        driver.save_screenshot(f"{user['name']}_{mode}_error.png")
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")

def presensi(user, mode):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(URL_LOGIN)
        logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")

        login(driver, user)
        time.sleep(5)  # tunggu redirect selesai

        lakukan_presensi(driver, user, mode)

    finally:
        driver.quit()

if __name__ == "__main__":
    now = now_jkt()
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} (Asia/Jakarta)")

    for user in USERS:
        if now.strftime("%H:%M") == JADWAL["check_in"]:
            presensi(user, "check_in")
        elif now.strftime("%H:%M") == JADWAL["check_out"]:
            presensi(user, "check_out")
        else:
            logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
