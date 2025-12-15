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
    - перечисляем все reg_method_name и reg_method_checkbox
    - находим индекс с текстом "Аудиозвонок"
    - тапаем по центру соответствующего checkbox через adb (MEmu adb)
    """
    adb = r"C:\Program Files\Microvirt\MEmu\adb.exe"
    try:
        names = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/reg_method_name")')
        boxes = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.whatsapp:id/reg_method_checkbox")')
        if not names or not boxes:
            print("MISS: нет reg_method_name или reg_method_checkbox")
            return False

        target_idx = None
        for idx, el in enumerate(names):
            try:
                txt = el.text
            except Exception:
                txt = ""
            print(f"[{idx}] reg_method_name = '{txt}'")
            if txt.strip() == "Аудиозвонок":
                target_idx = idx

        if target_idx is None or target_idx >= len(boxes):
            print("MISS: 'Аудиозвонок' не найден среди reg_method_name")
            return False

        box = boxes[target_idx].rect
        tap_x = box["x"] + box["width"] // 2
        tap_y = box["y"] + box["height"] // 2
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
