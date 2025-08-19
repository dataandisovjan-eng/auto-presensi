import os
import time
import datetime
import sys
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === CEK HARI LIBUR DAN WEEKEND ===
def is_holiday():
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        url = "https://raw.githubusercontent.com/guangrei/APIHariLibur/main/calendar.json"
        data = requests.get(url).json()
        if today in data and data[today]['holiday']:
            print("📌 Hari ini libur nasional:", data[today]['deskripsi'])
            return True
    except Exception as e:
        print("⚠️ Gagal cek API Hari Libur:", e)
    return False

today_num = datetime.datetime.today().weekday()  # Senin=0 ... Minggu=6
if today_num >= 5:  # Sabtu/Minggu
    print("🚫 Hari ini weekend, tidak perlu presensi")
    sys.exit()

if is_holiday():
    print("🚫 Hari ini libur nasional, tidak perlu presensi")
    sys.exit()

# === SETUP SELENIUM HEADLESS ===
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

wait = WebDriverWait(driver, 20)

# === LOGIN KE WEBSITE ===
driver.get("https://dani.perhutani.co.id")

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

driver.find_element(By.NAME, "username").send_keys(username)
driver.find_element(By.NAME, "password").send_keys(password, Keys.RETURN)

print("✅ Login berhasil")

# === HANDLE POPUP NEXT/FINISH SEBELUM PRESENSI ===
try:
    while True:
        # Tunggu kalau ada tombol Next/Finish
        popup_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.swal2-confirm")))
        btn_text = popup_btn.text.strip().lower()
        if "next" in btn_text:
            print("➡️ Klik Next")
            popup_btn.click()
            time.sleep(1)
        elif "finish" in btn_text:
            print("✅ Klik Finish")
            popup_btn.click()
            time.sleep(1)
            break
        else:
            print("ℹ️ Popup tidak dikenal:", btn_text)
            popup_btn.click()
            time.sleep(1)
except Exception as e:
    print("⚠️ Tidak ada popup Next/Finish:", e)

# === KLIK TOMBOL PRESENSI (HALAMAN UTAMA) ===
try:
    presensi_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")))
    presensi_btn.click()
    print("🟠 Klik tombol presensi utama")
    time.sleep(2)
except Exception as e:
    print("❌ Gagal klik tombol presensi utama:", e)
    driver.quit()
    sys.exit()

# === KLIK TOMBOL PRESENSI DI POPUP TERAKHIR ===
try:
    popup_presensi = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Klik disini untuk presensi')]")))
    popup_presensi.click()
    print("✅ Presensi berhasil")
    time.sleep(2)
except Exception as e:
    print("❌ Gagal klik tombol presensi popup:", e)

driver.quit()
