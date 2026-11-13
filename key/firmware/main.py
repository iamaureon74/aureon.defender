# Aureon Key - MicroPython firmware for Raspberry Pi Pico / Pico 2 (micropython/micropython).
#
# A USB companion that physically protects the laptop:
#   * PANIC button (GP15 -> GND): instantly lock the laptop
#   * TAMPER input (GP14 reed switch / lid magnet, open = tampered): lock + log
#   * Heartbeat: host agent locks the laptop if the Key is pulled out (walk-away lock)
#   * Onboard LED shows state.
# Talks to aureon/keyagent.py over USB serial (CDC). Line protocol:
#   Key -> host:  "HB <n>", "LOCK panic", "LOCK tamper"
#   host -> Key:  "PING" -> "PONG"
#                 "ALERT"  -> fast-blink until the panic button is pressed (acknowledge)
#                             sent by hidguard (rogue keyboard) and keyagent (HIGH analyst report)
import sys
import time
import select
from machine import Pin

led = Pin("LED", Pin.OUT)
panic = Pin(15, Pin.IN, Pin.PULL_UP)
tamper = Pin(14, Pin.IN, Pin.PULL_UP)

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)


def send(msg):
    sys.stdout.write(msg + "\n")


def debounced(pin, level=0, ms=40):
    if pin.value() != level:
        return False
    time.sleep_ms(ms)
    return pin.value() == level


n = 0
last_hb = time.ticks_ms()
tamper_latched = False
alerting = False
while True:
    if alerting:
        led.toggle()
        time.sleep_ms(60)
        if debounced(panic):  # press = acknowledge alert, not panic
            alerting = False
            send("ACK")
            while panic.value() == 0:
                time.sleep_ms(20)
            continue
    elif debounced(panic):
        send("LOCK panic")
        for _ in range(6):
            led.toggle()
            time.sleep_ms(80)
        while panic.value() == 0:
            time.sleep_ms(20)

    if debounced(tamper, level=1) and not tamper_latched:
        tamper_latched = True
        send("LOCK tamper")
    elif tamper.value() == 0:
        tamper_latched = False

    if poll.poll(0):
        line = sys.stdin.readline().strip()
        if line == "PING":
            send("PONG")
        elif line == "ALERT":
            alerting = True

    if time.ticks_diff(time.ticks_ms(), last_hb) > 1000:
        n += 1
        send("HB %d" % n)
        if not alerting:
            led.toggle()
        last_hb = time.ticks_ms()
    time.sleep_ms(10)
