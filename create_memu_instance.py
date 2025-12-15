import subprocess
import os
import sys
import re
import time

# Путь к memuc.exe (CLI для управления MEmu)
# Обычно лежит там же, где и MEmu.exe
MEMUC_PATH = r"C:\Program Files\Microvirt\MEmu\memuc.exe"

def run_memuc(args):
    """Запуск команды memuc и возврат вывода"""
    if not os.path.exists(MEMUC_PATH):
        print(f"❌ Ошибка: не найден memuc.exe по пути: {MEMUC_PATH}")
        sys.exit(1)
        
    cmd = [MEMUC_PATH] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout.strip()

def main():
    print("🚀 Создаю новый инстанс MEmu...")

    # 1. Создаем Android 9.0 64-bit (код версии 96)
    # Коды: 51=Android 5, 71=Android 7 (32), 76=Android 7 (64), 96=Android 9 (64)
    output = run_memuc(["create", "96"])
    
    # Парсим индекс из ответа "SUCCESS: create vm finished. index: 5"
    match = re.search(r"index:\s*(\d+)", output)
    if not match:
        print(f"❌ Не удалось создать инстанс. Вывод: {output}")
        return

    index = int(match.group(1))
    print(f"✓ Инстанс создан. Индекс: {index}")

    # 2. Настраиваем производительность (2 CPU, 1536 RAM)
    print("⚙️  Настраиваю CPU/RAM...")
    run_memuc(["setconfigex", "-i", str(index), "cpus", "2"])
    run_memuc(["setconfigex", "-i", str(index), "memory", "1536"])

    # 3. Настраиваем разрешение (720x1280, 240dpi, Mobile)
    print("⚙️  Настраиваю экран...")
    run_memuc(["setconfigex", "-i", str(index), "is_custom_resolution", "1"])
    run_memuc(["setconfigex", "-i", str(index), "resolution_width", "720"])
    run_memuc(["setconfigex", "-i", str(index), "resolution_height", "1280"])
    run_memuc(["setconfigex", "-i", str(index), "v_dpi", "240"])

    # 4. Настраиваем рендер (DirectX)
    # graphics_render_mode: 0 = OpenGL, 1 = DirectX
    print("⚙️  Включаю DirectX...")
    run_memuc(["setconfigex", "-i", str(index), "graphics_render_mode", "1"])

    # 5. Запускаем
    print(f"▶️  Запускаю инстанс {index}...")
    run_memuc(["start", "-i", str(index)])

    # 6. Вычисляем ADB порт
    # Базовый порт 21503, шаг 10. Индекс 0 -> 21503, Индекс 1 -> 21513
    adb_port = 21503 + (index * 10)
    device_name = f"127.0.0.1:{adb_port}"

    # 7. Устанавливаем SuperProxy (или другой apk для прокси)
    apk_proxy = "superproxy.apk"
    if os.path.exists(apk_proxy):
        print(f"🌍 Устанавливаю {apk_proxy}...")
        # memuc installapp -i <index> <apk_path>
        run_memuc(["installapp", "-i", str(index), os.path.abspath(apk_proxy)])
        print(f"✓ Proxy приложение установлено")
    else:
        print(f"⚠️  Файл {apk_proxy} не найден, пропуск установки прокси-клиента")

    print("\n" + "="*40)
    print(f"✅ Готово! Новый девайс запущен.")
    print("="*40)
    # Вывод в формате, готовом для вставки в main.py
    print(f'MEMU_DEVICE = "{device_name}"')
    print("="*40)

if __name__ == "__main__":
    main()

