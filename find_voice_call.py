import os
import sys
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


def try_find_voice_call(driver):
    """
    Кликаем radio "Аудиозвонок" без фолбеков:
    - Находим строку, где reg_method_name = "Аудиозвонок"
    - Внутри неё ищем reg_method_checkbox и жмём
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
        radio.click()
        print("✓ Клик по radio 'Аудиозвонок'")
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
        ok_voice = try_find_voice_call(driver)
        if not ok_voice:
            print("Voice call NOT clicked")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
