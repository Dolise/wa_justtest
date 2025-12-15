import subprocess
import os
import sys
import re

MEMUC_PATH = r"C:\Program Files\Microvirt\MEmu\memuc.exe"
ADB_PATH = r"C:\Program Files\Microvirt\MEmu\adb.exe"

def run_memuc(args):
    cmd = [MEMUC_PATH] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout.strip()

def main():
    print("🔍 Диагностика Root в MEmu...")
    
    # 1. Список инстансов
    print("\n1. Список инстансов:")
    list_out = run_memuc(["list"])
    print(list_out)
    
    # Пытаемся найти запущенный инстанс
    running_idx = None
    for line in list_out.splitlines():
        if line.strip():
            parts = line.split(',')
            if len(parts) > 2 and "1" in parts[2]: # 1 значит запущен
                running_idx = parts[0]
                print(f"✓ Найден запущенный инстанс: Index {running_idx}")
                break
    
    if not running_idx:
        print("⚠️ Нет запущенных инстансов. Беру индекс 0 для проверки конфига.")
        running_idx = "0"

    # 2. Читаем конфиг
    print(f"\n2. Конфиг инстанса {running_idx}:")
    # Пробуем получить все известные ключи рута
    keys = ["is_root_mode", "root_mode", "enable_root", "root"]
    for k in keys:
        val = run_memuc(["getconfigex", "-i", running_idx, k])
        print(f"   {k} = {val}")

    # 3. Пробуем ADB ROOT
    print("\n3. Попытка переключить ADB в root режим:")
    try:
        subprocess.run([ADB_PATH, "root"], check=False)
        print("   Команда `adb root` выполнена. Проверяем `adb shell whoami`...")
        res = subprocess.run([ADB_PATH, "shell", "whoami"], capture_output=True, text=True)
        print(f"   Результат whoami: {res.stdout.strip()}")
        
        if "root" in res.stdout:
            print("🎉 УРА! ADB получил Root права!")
        else:
            print("❌ ADB все еще не root.")
    except Exception as e:
        print(f"   Ошибка ADB: {e}")

if __name__ == "__main__":
    main()

