import os
import sys
import subprocess
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy


def connect_driver(device_name: str):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": device_name,
        "udid": device_name,
        "appPackage": "com.whatsapp",
        "appActivity": "com.whatsapp.Main",
        "autoLaunch": False,
        "appWaitActivity": "*",
        "noReset": True,
        "fullReset": False,
        "newCommandTimeout": 1200,
    }
    return webdriver.Remote("http://localhost:4723", caps)


def try_find_voice_call(driver, device):
    """
    Кликаем вариант "Аудиозвонок":
    - ищем строку (reg_method_name="Аудиозвонок")
    - берём чекбокс reg_method_checkbox
    - тапаем по центру через adb (использует ADB_PATH или просто adb)
    """
    try:
        row = driver.find_element(
            AppiumBy.XPATH,
            '//android.widget.LinearLayout[.//android.widget.TextView[@resource-id="com.whatsapp:id/reg_method_name" and @text="Аудиозвонок"]]'
        )
        radio = row.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().resourceId("com.whatsapp:id/reg_method_checkbox")'
        )
        rect = radio.rect
        tap_x = rect["x"] + rect["width"] // 2
        tap_y = rect["y"] + rect["height"] // 2
        adb = r"C:\Program Files\Microvirt\MEmu\adb.exe"
        subprocess.run([adb, "-s", device, "shell", "input", "tap", str(tap_x), str(tap_y)], check=True)
        print(f"✓ adb tap 'Аудиозвонок' @ ({tap_x},{tap_y}) через {adb}")
        return True
    except Exception as e:
        print(f"MISS 'Аудиозвонок': {e}")
        return False


def try_find_continue(driver):
    selectors = [
        'new UiSelector().resourceId("com.whatsapp:id/continue_button").clickable(true)',
        'new UiSelector().text("ПРОДОЛЖИТЬ").clickable(true)',
        'new UiSelector().text("Продолжить").clickable(true)',
        'new UiSelector().text("CONTINUE").clickable(true)',
    ]
    for sel in selectors:
        try:
            el = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, sel)
            print(f"FOUND continue by: {sel}")
            el.click()
            print("CLICKED continue")
            return True
        except Exception as e:
            print(f"MISS  continue by: {sel} -> {e}")
    return False


def main():
    device = os.getenv("MEMU_DEVICE", "127.0.0.1:21613")
    try:
        driver = connect_driver(device)
    except Exception as e:
        print(f"Cannot connect driver: {e}")
        sys.exit(1)

    try:
        ok_voice = try_find_voice_call(driver, device)
        if not ok_voice:
            print("Voice call NOT clicked")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
