"""
common/treasurai_call.py — pemanggil TreasurAI yang TAHAN HANG.

Masalah: read-timeout `requests` tidak selalu memutus koneksi yang di-throttle
(server menahan koneksi tanpa jeda-byte bersih), sehingga satu call bisa
menggantung menahan seluruh batch. Helper ini membungkus call dalam thread
dengan batas wall-clock keras (hard timeout) + cooldown adaptif saat gagal,
agar batch SELALU maju.

Reasoning tetap memakai TreasurAI oss120b — helper ini hanya transport.
"""
import threading
import time

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def call_with_timeout(url, payload, headers,
                      connect_to=10, read_to=35, hard_to=45,
                      retries=2, cooldown=20):
    """Return (response_or_None, err_str_or_None).

    - hard_to: batas wall-clock per percobaan. Lewat ini → dianggap gagal,
      thread ditinggalkan (daemon) dan lanjut.
    - cooldown: jeda setelah kegagalan (memberi server pulih dari throttle).
    """
    for attempt in range(retries + 1):
        box = {}

        def _do():
            try:
                box["r"] = requests.post(
                    url, json=payload, headers=headers,
                    timeout=(connect_to, read_to), verify=False,
                )
            except Exception as e:  # noqa
                box["e"] = str(e)[:120]

        th = threading.Thread(target=_do, daemon=True)
        th.start()
        th.join(hard_to)

        if not th.is_alive() and "r" in box:
            return box["r"], None

        # gagal (hang melewati hard_to, atau exception)
        err = "hard_timeout" if th.is_alive() else box.get("e", "unknown")
        if attempt < retries:
            time.sleep(cooldown)  # beri server waktu pulih sebelum retry
    return None, err
