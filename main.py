import os
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== Cek Hari Libur Nasional =====
def is_holiday():
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year
    month = datetime.now().month
    
    try:
        url = f"https://api-harilibur.vercel.app/api?month={month}&year={year}"
        response = requests.get(url, timeout=10)
        data = response.json()

        for holiday in data:
            if holiday.get("is_national_holiday") and holiday["holiday_date"] == today:
                print(f"❌ Hari ini libur nasional: {holiday['holiday_name']}")
                return True
        return False
    except Exception as e:
        print(f"⚠️ Gagal cek API Hari Libur: {e}")
        return False

# ===== Setup Selenium =====
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

# ===== Proses Presensi =====
def presensi():
    username = os.getenv("PRESENSI_USERNAME")
    password = os.getenv("PRESENSI_PASSWORD")
    url = "https://dani.perhutani.co.id"

    if not username or not password:
        print("❌ Username/password tidak ditemukan di Secrets.")
        return

    driver = setup_driver()
    wait = WebDriverWait(driver, 20)

    try:
        print("🔗 Membuka website...")
        driver.get(url)

        # Login
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)
        driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
        print("✅ Login berhasil")

        # Handle popup "Next" sampai muncul "Finish"
        while True:
            try:
                next_btn = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Next')]"))
                )
                next_btn.click()
                print("➡️ Klik Next")
                time.sleep(1)
            except:
                try:
                    finish_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Finish')]")
                    finish_btn.click()
                    print("✅ Klik Finish")
                except:
                    print("ℹ️ Tidak ada popup Next/Finish lagi.")
                break

        # Klik tombol utama presensi
        presensi_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))
        )
        presensi_btn.click()
        print("🟠 Klik tombol presensi utama")

        # Klik tombol popup presensi
        popup_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]"))
        )
        popup_btn.click()
        print("✅ Presensi berhasil")

    except Exception as e:
        print(f"❌ Error saat presensi: {e}")
    finally:
        driver.quit()

# ===== Main Program =====
if __name__ == "__main__":
    today = datetime.now().strftime("%A")

    # Skip weekend
    if today in ["Saturday", "Sunday"]:
        print("❌ Hari ini weekend, skip presensi.")
        exit(0)

    # Skip libur nasional
    if is_holiday():
        exit(0)

    # Jalankan presensi
    presensi()
