# -*- coding: utf-8 -*-
import webbrowser
import sys
import os
import struct
import time
import types
#
import pyautogui
import numpy as np
import cv2
#
from win10toast import ToastNotifier
from win32gui import Shell_NotifyIcon, NIM_DELETE, GetWindowText, GetForegroundWindow, GetWindowRect
from win32api import PostQuitMessage
from PIL import ImageGrab
from threading import Thread
from infi.systray import SysTrayIcon


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
  
def app_pause(systray):
    global is_stop
    is_stop = False if is_stop is True else True
    # print ("Is Pause: " + str(is_stop))
    if is_stop is True:
        systray.update(
            hover_text=app + " - On Pause") 
    else:
        systray.update(
            hover_text=app)         

def app_destroy(systray):
    # print("Exit app")
    sys.exit()
    
def app_about(systray):
    # print("github.com/YECHEZ/wow-fish-bot")
    webbrowser.open('https://github.com/YECHEZ/wow-fish-bot')

if __name__ == "__main__":
    is_stop = True
    flag_exit = False
    lastx = 0
    lasty = 0
    smooth_x = 0.0
    smooth_y = 0.0
    smooth_init = False
    is_block = False
    new_cast_time = 0
    recast_time = 40
    wait_mes = 0
    # A real fish-bite splash dips the cork down by more than this many pixels
    # below its smoothed resting position.  Natural wave bobbing stays well
    # under this value; a genuine splash typically exceeds it.
    SPLASH_THRESHOLD = 15
    # EMA weight used to track the cork's resting position.  A small value
    # (0.2) lets the average follow slow drift while ignoring sudden dips.
    SMOOTH_ALPHA = 0.2
    app = "WoW Fish BOT by YECHEZ"
    link = "github.com/YECHEZ/wow-fish-bot"
    app_ico = resource_path('wow-fish-bot.ico')
    menu_options = (("Start/Stop", None, app_pause),
                    (link, None, app_about),)
    systray = SysTrayIcon(app_ico, app, 
                          menu_options, on_quit=app_destroy)
    systray.start()
    toaster = ToastNotifier()
    # Fix: win10toast's on_destroy returns None instead of 0, causing
    # "WNDPROC return value cannot be converted to LRESULT" and a cascading
    # "TypeError: WPARAM is simple, so must be an int object (got NoneType)".
    def _on_destroy_fixed(self, hwnd, msg, wparam, lparam):
        nid = (self.hwnd, 0)
        Shell_NotifyIcon(NIM_DELETE, nid)
        PostQuitMessage(0)
        return 0
    toaster.on_destroy = types.MethodType(_on_destroy_fixed, toaster)
    toaster.show_toast(app,
                       link,
                       icon_path=app_ico,
                       duration=5)    
    while flag_exit is False:
        if is_stop == False:
            if GetWindowText(GetForegroundWindow()) != "World of Warcraft":
                if wait_mes == 5:
                    wait_mes = 0
                    toaster.show_toast(app,
                                       "Waiting for World of Warcraft"
                                       + " as active window",
                                       icon_path=app_ico,
                                       duration=5,
                                       threaded=True)                  
                # print("Waiting for World of Warcraft as active window")
                systray.update(
                    hover_text=app
                    + " - Waiting for World of Warcraft as active window")
                wait_mes += 1
                time.sleep(2)
            else:
                systray.update(hover_text=app)
                rect = GetWindowRect(GetForegroundWindow())
                
                if is_block == False:
                    lastx = 0
                    lasty = 0
                    smooth_x = 0.0
                    smooth_y = 0.0
                    smooth_init = False
                    pyautogui.press('1')
                    # print("Fish on !")
                    new_cast_time = time.time()
                    is_block = True
                    time.sleep(2)
                else:
                    fish_area = (rect[0], (rect[1] + rect[3]) // 2, rect[2], rect[3])
    
                    img = ImageGrab.grab(fish_area)
                    img_np = np.array(img)
    
                    frame = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
                    frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
                    # Detect the red/orange feather of the fishing cork.
                    # Red wraps around in HSV, so two ranges are needed:
                    # lower red (H 0-15) and upper red (H 155-180).
                    # Using saturation >= 100 and value >= 50 avoids matching
                    # the bright-but-desaturated water reflections that caused
                    # false positives with the old brightness-only approach.
                    h_min_red1 = np.array((0, 100, 50), np.uint8)
                    h_max_red1 = np.array((15, 255, 255), np.uint8)
                    h_min_red2 = np.array((155, 100, 50), np.uint8)
                    h_max_red2 = np.array((180, 255, 255), np.uint8)
    
                    mask_red1 = cv2.inRange(frame_hsv, h_min_red1, h_max_red1)
                    mask_red2 = cv2.inRange(frame_hsv, h_min_red2, h_max_red2)
                    mask = cv2.bitwise_or(mask_red1, mask_red2)
    
                    # Morphological cleanup: remove isolated noise pixels, then
                    # expand the remaining blob so the centroid is stable.
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    mask = cv2.dilate(mask, kernel, iterations=2)
    
                    moments = cv2.moments(mask, 1)
                    dM01 = moments['m01']
                    dM10 = moments['m10']
                    dArea = moments['m00']
    
                    b_x = 0
                    b_y = 0
    
                    # Require a minimum blob area to ignore stray red pixels.
                    if dArea > 100:
                        b_x = int(dM10 / dArea)
                        b_y = int(dM01 / dArea)
                    if lastx > 0 and lasty > 0 and b_x > 0 and b_y > 0:
                        # Initialise the smoothed resting position on the
                        # first valid detection after a new cast.
                        if not smooth_init:
                            smooth_x = float(b_x)
                            smooth_y = float(b_y)
                            smooth_init = True
                        # A real splash is a sudden downward dip well below
                        # the smoothed resting position.  In image coordinates
                        # y increases downward, so a dip means b_y exceeds
                        # smooth_y by at least SPLASH_THRESHOLD pixels.
                        # Normal wave bobbing produces much smaller deltas and
                        # does not consistently push the cork downward, so
                        # this avoids the false catches the old 5-pixel
                        # any-direction check caused.
                        if b_y - smooth_y > SPLASH_THRESHOLD:
                            is_block = False
                            if b_x < 1: b_x = lastx
                            if b_y < 1: b_y = lasty
                            pyautogui.moveTo(b_x + fish_area[0], b_y + fish_area[1], 0.3)
                            pyautogui.keyDown('shiftleft')
                            pyautogui.mouseDown(button='right')
                            pyautogui.mouseUp(button='right')
                            pyautogui.keyUp('shiftleft')
                            # print("Catch !")
                            time.sleep(5)
                        else:
                            # Update the EMA so it slowly tracks the cork's
                            # natural drift without being fooled by a fast dip.
                            # Stored as float to preserve precision across updates.
                            smooth_x += SMOOTH_ALPHA * (b_x - smooth_x)
                            smooth_y += SMOOTH_ALPHA * (b_y - smooth_y)
                    lastx = b_x
                    lasty = b_y
                    
                    # show windows with mask
                    # cv2.imshow("fish_cork_mask", mask)
                    # cv2.imshow("fish_frame", frame)
    
                    if time.time() - new_cast_time > recast_time:
                        # print("New cast if something wrong")
                        is_block = False               
            if cv2.waitKey(1) == 27:
                break
        else:
            # print("Pause")
            systray.update(hover_text=app + " - On Pause")   
            time.sleep(2)