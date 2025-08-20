import os
import json
import logging
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(
    filename="presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

def get_now(tzname):
    tz = pytz.timezone(tzname)
    return datetime.now(tz)

def presensi(user, mode):
    username = os.getenv(user["secret_user"])
    password = os.getenv(user["secret_pass"])
    if not username or not password:
        logging.warning(f"[{user['name']}] ⚠️ Username/password tidak ditemukan di Secrets")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
        driver.get("https://dani.perhutani.co.id/login")

        # Save screenshot login page (debug)
        os.makedirs("screenshots", exist_ok=True)
        driver.save_screenshot(f"screenshots/{user['id']}_loginpage.png")

        # Input NPK (username) dengan fallback
        try:
            npk_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        except:
            try:
                npk_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
            except:
                npk_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='NPK']")))
        npk_input.clear()
        npk_input.send_keys(username)

        # Input password dengan fallback
        try:
            pass_input = driver.find_element(By.NAME, "password")
        except:
            try:
                pass_input = driver.find_element(By.ID, "password")
            except:
                pass_input = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
        pass_input.clear()
        pass_input.send_keys(password)

        # Klik login
        login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
        login_btn.click()

        logging.info(f"[{user['name']}] ✅ Berhasil login (dummy aksi presensi: {mode})")
        driver.save_screenshot(f"screenshots/{user['id']}_{mode}.png")

    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")
        driver.save_screenshot(f"screenshots/{user['id']}_error.png")

    finally:
        driver.quit()

def main():
    cfg = load_config()
    now = get_now(cfg["timezone"])
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} ({cfg['timezone']})")

    # Cek apakah ada force run
    force_user = os.getenv("FORCE_USER")
    force_mode = os.getenv("FORCE_MODE")

    for user in cfg["users"]:
        if force_user and force_user != user["id"]:
            logging.info(f"[{user['name']}] Skip (force untuk {force_user})")
            continue

        if force_mode:
            presensi(user, force_mode)
            continue

        # Presensi sesuai jadwal
        tnow = now.strftime("%H:%M")
        if tnow == user["check_in"]:
            presensi(user, "check_in")
        elif tnow == user["check_out"]:
            presensi(user, "check_out")
        else:
            logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")

if __name__ == "__main__":
    main()
