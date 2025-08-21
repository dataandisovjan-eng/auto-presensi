import os
import time
import logging
import pytz
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# === Konfigurasi Logging ===
logging.basicConfig(
    filename="presensi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# === Data User ===
USERS = [
    {
        "name": "Andi",  # user1 diganti Andi
        "username": os.getenv("USER1_USERNAME"),
        "password": os.getenv("USER1_PASSWORD"),
    },
    {
        "name": "Bu Sari",  # user2 tetap
        "username": os.getenv("USER2_USERNAME"),
        "password": os.getenv("USER2_PASSWORD"),
    },
]

# === Jadwal Default Presensi ===
JADWAL = {
    "check_in": "05:30",   # dimajukan
    "check_out": "16:05",
}

# === Helper Waktu ===
def now_jkt():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

# === Fungsi Presensi ===
def presensi(user, mode):
    logging.info(f"[{user['name']}] 🌐 Membuka halaman login...")
    try:
        chrome_opts = Options()
        chrome_opts.add_argument("--headless=new")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_opts)

        driver.get("https://dani.perhutani.co.id/login")

        wait = WebDriverWait(driver, 15)

        # Login form
        npk_input = wait.until(EC.presence_of_element_located((By.NAME, "npk")))
        npk_input.clear()
        npk_input.send_keys(user["username"])

        password_input = driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(user["password"])

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Handle popup "Next" sampai ketemu "Finish"
        while True:
            try:
                next_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Next')]"))
                )
                next_btn.click()
                time.sleep(1)
            except:
                try:
                    finish_btn = driver.find_element(By.XPATH, "//button[contains(., 'Finish')]")
                    finish_btn.click()
                    time.sleep(1)
                    break
                except:
                    break

        # Klik tombol presensi pertama
        presensi_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'klik disini untuk presensi')]"))
        )
        presensi_btn.click()
        time.sleep(2)

        # Popup konfirmasi presensi
        confirm_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'klik disini untuk presensi')]"))
        )
        confirm_btn.click()
        time.sleep(2)

        # Screenshot hasil
        ss_file = f"screenshot_{user['name']}_{mode}.png"
        driver.save_screenshot(ss_file)

        logging.info(f"[{user['name']}] ✅ Berhasil {mode}")
        driver.quit()

    except Exception as e:
        logging.error(f"[{user['name']}] ❌ Error saat presensi: {e}")
        try:
            ss_file = f"error_{user['name']}_{mode}.png"
            driver.save_screenshot(ss_file)
        except:
            pass
        driver.quit()

# === Main Logic ===
if __name__ == "__main__":
    now = now_jkt()
    logging.info(f"⏰ Sekarang {now.strftime('%Y-%m-%d %H:%M')} (Asia/Jakarta)")

    force_user = os.getenv("FORCE_USER", "").strip()
    force_mode = os.getenv("FORCE_MODE", "").strip()

    # 🔧 Default jika manual run tanpa input
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        if not force_user:
            force_user = "all"
        if not force_mode:
            # Default check_in pagi, check_out sore
            if now.hour >= 12:
                force_mode = "check_out"
            else:
                force_mode = "check_in"

    if force_mode and force_user:
        logging.info(f"⚡ Manual run: user={force_user}, mode={force_mode}")
        for user in USERS:
            if force_user.lower() == "all" or force_user.lower() == user["name"].lower():
                presensi(user, force_mode)
    else:
        for user in USERS:
            if now.strftime("%H:%M") == JADWAL["check_in"]:
                presensi(user, "check_in")
            elif now.strftime("%H:%M") == JADWAL["check_out"]:
                presensi(user, "check_out")
            else:
                logging.info(f"[{user['name']}] Skip (bukan jadwal user ini)")
