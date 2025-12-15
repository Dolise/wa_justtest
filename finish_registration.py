import subprocess
import time
import os
import sys
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy

# Путь к ADB
ADB_PATH = os.getenv("ADB_PATH") or r"C:\Program Files\Microvirt\MEmu\adb.exe"

def get_first_device():
    try:
        res = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
        import re
        match = re.search(r"(127\.0\.0\.1:2\d{4})\s+device", res.stdout)
        if match:
            return match.group(1)
    except:
        pass
    return "127.0.0.1:21503"

def connect_driver(device_name):
    print(f"🔌 Подключаюсь к {device_name}...")
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": device_name,
        "udid": device_name,
        "appPackage": "com.whatsapp",
        "appActivity": "com.whatsapp.Main",
        "autoLaunch": False,
        "noReset": True,
        "fullReset": False,
        "newCommandTimeout": 600,
    }
    return webdriver.Remote("http://localhost:4723", caps)

def finish_reg(driver):
    print("⏳ Ищу поле ввода имени...")
    
    # 1. Ввод имени
    try:
        # Обычно это EditText
        # Либо id: com.whatsapp:id/registration_name
        name_input = None
        selectors = [
            'new UiSelector().resourceId("com.whatsapp:id/registration_name")',
            'new UiSelector().className("android.widget.EditText")',
            'new UiSelector().textContains("Type your name here")',
            'new UiSelector().textContains("Введите ваше имя")',
        ]
        
        for sel in selectors:
            try:
                els = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                if els:
                    name_input = els[0]
                    print(f"✓ Найдено поле имени по селектору: {sel}")
                    break
            except: pass
            
        if name_input:
            name_input.click()
            name_input.clear()
            name_input.send_keys("Alex")
            print("✓ Имя 'Alex' введено")
            time.sleep(1)
            
            # Вместо hide_keyboard пробуем нажать 'Back' один раз (скрывает клаву)
            # или 'Enter'
            try:
                # 66 = ENTER / Action Down
                driver.press_keycode(66)
                print("✓ Нажат Enter (код 66)")
            except: pass
            
        else:
            print("⚠️ Поле имени не найдено")
            
    except Exception as e:
        print(f"⚠️ Ошибка ввода имени: {e}")

    # 2. Нажатие NEXT
    print("⏳ Ищу кнопку 'Next' / 'Далее'...")
    try:
        next_btn = None
        selectors = [
            'new UiSelector().resourceId("com.whatsapp:id/register_name_accept")', # Кнопка Next на экране имени
            'new UiSelector().text("NEXT")',
            'new UiSelector().text("Next")',
            'new UiSelector().text("ДАЛЕЕ")',
            'new UiSelector().text("Далее")',
        ]
        
        for sel in selectors:
            try:
                els = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, sel)
                if els:
                    next_btn = els[0]
                    print(f"✓ Найдена кнопка Next по селектору: {sel}")
                    break
            except: pass
            
        if next_btn:
            next_btn.click()
            print("✓ Кнопка Next нажата")
            time.sleep(3)
        else:
            print("⚠️ Кнопка Next не найдена")

    except Exception as e:
        print(f"⚠️ Ошибка нажатия Next: {e}")
        
    # 3. Иногда бывает экран "Create a passkey" -> Ski
    
    # 4. Иногда бывает "Initializing..." долго
    print("🏁 Скрипт завершен")

def main():
    device = get_first_device()
    print(f"📱 Device: {device}")
    
    driver = None
    try:
        driver = connect_driver(device)
        finish_reg(driver)
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
