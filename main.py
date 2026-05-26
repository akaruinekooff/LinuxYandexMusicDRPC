#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from threading import Thread

import dbus
import pystray
from PIL import Image
from colorama import Fore, init
from pypresence import Presence
from yandex_music import Client
from pypresence.types import ActivityType
init(autoreset=True)

CLIENT_ID = "1217562797999784007"
UPDATE_INTERVAL = 1
ENABLE_YANDEX = True

# подключаем яндекс музыку
client = None
if ENABLE_YANDEX:
    try:
        client = Client().init()
        print(Fore.GREEN + "[+] Яндекс.Музыка API подключен")
    except Exception as e:
        print(Fore.RED + f"[!] не удалось подключиться к Yandex Music: {e}")

# подключаем Discord RPC
rpc = None
try:
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    print(Fore.CYAN + "[+] Discord RPC запущен")
except Exception as e:
    print(Fore.RED + f"[!] не удалось подключиться к Discord: {e}")




def get_mpris_track():
    """получаем текущий трек через мприз"""
    try:
        session_bus = dbus.SessionBus()
        players = [service for service in session_bus.list_names() if service.startswith('org.mpris.MediaPlayer2.')]
        if not players:
            return None

        # берём первый активный плеер
        for player_name in players:
            player = session_bus.get_object(player_name, '/org/mpris/MediaPlayer2')
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')
            status = props.Get('org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
            identity = props.Get('org.mpris.MediaPlayer2', 'Identity')
            if not ("yandex" in identity.lower()):
                continue
            meta = props.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
            artist = ', '.join(meta.get('xesam:artist', []))
            title = meta.get('xesam:title', 'Unknown')
            album = meta.get('xesam:album', '')
            if artist != "":
                return {
                    "artist": artist,
                    "title": title,
                    "album": album,
                    "status": status,
                    "player": player_name.split('.')[-1]
                }
        return None
    except Exception as e:
        print(Fore.RED + f"[MPRIS error] {e}")
        return None




def toggle_autostart(app_name='YaMusicRPC', command='python3 /path/to/linux_yandex_music_rpc.py'):
    """включение, выключение автозапуска"""
    path = os.path.expanduser(f'~/.config/autostart/{app_name}.desktop')
    if os.path.exists(path):
        os.remove(path)
        print(Fore.YELLOW + "⛔ автозапуск выключен")
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(f'''[Desktop Entry]
Type=Application
Exec={command}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name={app_name}
''')
        print(Fore.GREEN + "✅ автозапуск включён")

def update_presence_loop():
    """основной цикл обновления Discord RPC"""
    last_title = None
    start_time = None

    while True:
        track = get_mpris_track()
        if track:
            artist = track["artist"]
            title = track["title"]
            album = track["album"]
            status = track["status"]

            if title != last_title:
                start_time = int(time.time()) if status == "Playing" else None
                print(Fore.MAGENTA + f"[{datetime.now().strftime('%H:%M:%S')}] 🎧 {artist} — {title} ({status})")
                last_title = title

            if rpc:
                try:
                    # получаем обложку из Яндекс API (если подключён)
                    large_image = "yandex_music_logo"
                    large_text = f"{artist} — {title}"

                    if ENABLE_YANDEX and client:
                        search = client.search(f"{artist} {title}")
                        if search and search.best:
                            try:
                                cover_uri = search.best.result.cover_uri
                                cover_url = f"https://{cover_uri.replace('%%', '200x200')}"
                                large_image = cover_url  # discord разрешает URL, если client_id твой
                                large_text = f"{album or 'Яндекс.Музыка'}"
                            except Exception:
                                pass

                    # создаём rpc
                    rpc.update(
                        activity_type=ActivityType.LISTENING,
                        details=f"🎵 {artist} — {title}",
                        state=f"💿 {album}" if album else "🎶 Yandex Music",
                        large_image=large_image,
                        large_text=large_text,
                        small_image="play" if status == "Playing" else "pause",
                        small_text="▶️  playing" if status == "Playing" else "⏸️ paused",
                        start=start_time
                    )

                except Exception as e:
                    print(Fore.RED + f"[RPC error] {e}")

        else:
            if rpc:
                rpc.clear()

        time.sleep(UPDATE_INTERVAL)

def create_tray_icon():
    """иконка в трее"""
    icon_image = Image.new("RGB", (64, 64), color=(255, 0, 0))

    def on_exit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Выход", on_exit)
    )
    title = "Яндекс Музыка RPC".encode('utf-8', errors='ignore').decode('latin-1', errors='ignore')
    icon = pystray.Icon("YaMusicRPC", icon_image, title, menu)
    icon.run()

if __name__ == "__main__":
    print(Fore.CYAN + "🐧 Linux Yandex Music RPC запущен!")
    Thread(target=create_tray_icon, daemon=True).start()
    update_presence_loop()
