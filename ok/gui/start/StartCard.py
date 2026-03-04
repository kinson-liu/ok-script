import os
import subprocess
import time
import zipfile
from ctypes import windll, wintypes
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from _ctypes import byref
from qfluentwidgets import FluentIcon, SettingCard, PushButton

from ok import Handler
from ok import Logger
from ok import og
from ok.gui.Communicate import communicate
from ok.gui.debug.DebugTab import capture
from ok.gui.widget.StatusBar import StatusBar

logger = Logger.get_logger(__name__)


class StartCard(SettingCard):
    show_choose_hwnd = Signal()
    hotkey_changed = Signal()

    def __init__(self, exit_event):
        super().__init__(og.config.get('gui_icon'), og.app.title, og.app.version)
        self.basic_options = og.executor.basic_options

        self.iconLabel.setFixedSize(30, 30)
        self.hBoxLayout.setAlignment(Qt.AlignVCenter)
        self.status_bar = StatusBar("test")
        self.status_bar.clicked.connect(self.status_clicked)

        self.hBoxLayout.addWidget(self.status_bar, 0, Qt.AlignLeft)
        self.hBoxLayout.addSpacing(6)

        self.open_install_folder_button = PushButton(FluentIcon.FOLDER, self.tr("Install Folder"), self)
        self.hBoxLayout.addWidget(self.open_install_folder_button, 0, Qt.AlignRight)
        self.open_install_folder_button.clicked.connect(self.open_install_folder)
        self.hBoxLayout.addSpacing(6)

        self.export_log_button = PushButton(FluentIcon.FEEDBACK, self.tr("Export Logs"), self)
        self.hBoxLayout.addWidget(self.export_log_button, 0, Qt.AlignRight)
        self.export_log_button.clicked.connect(self.export_logs)
        self.hBoxLayout.addSpacing(6)

        self.capture_button = PushButton(FluentIcon.ZOOM, self.tr("Capture"), self)
        self.hBoxLayout.addWidget(self.capture_button, 0, Qt.AlignRight)
        self.capture_button.clicked.connect(self.capture)
        self.hBoxLayout.addSpacing(6)

        self.start_button = PushButton(FluentIcon.PLAY, self.tr("Start"), self)
        self.hBoxLayout.addWidget(self.start_button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(6)

        self.hotkey_changed.connect(self.update_status)
        self.update_status()
        self.start_button.clicked.connect(self.clicked)
        communicate.executor_paused.connect(self.update_status)
        communicate.window.connect(self.update_status)
        communicate.task.connect(self.update_task)

        self.handler = Handler(exit_event, "StartCard")
        self.current_hotkey = "UNINIT"
        self._hotkey_press_time = 0  # 按下时间戳
        self._hotkey_vk = 0  # 当前热键的 VK 码
        self._long_press_threshold = 1.0  # 长按阈值（秒）
        self._long_press_triggered = False  # 是否已触发长按停止
        self.handler.post(self.check_hotkey, 0.1)
        logger.debug('basic_options.start/stop: {}'.format(self.basic_options.get('Start/Stop')))

    @staticmethod
    def capture():
        return capture(processor=og.config.get('screenshot_processor'))

    def status_clicked(self):
        if not og.executor.paused:
            if og.executor.current_task:
                communicate.tab.emit("onetime")
            elif og.executor.active_trigger_task_count():
                communicate.tab.emit("trigger")
            else:
                communicate.tab.emit("start")
            self.status_bar.show()

    @staticmethod
    def clicked():
        if not og.executor.paused:
            og.executor.pause()
        else:
            og.app.start_controller.start()

    @staticmethod
    def long_pressed():
        """长按热键：真正停止当前任务"""
        logger.info('hotkey long pressed, stopping current task')
        og.executor.stop_current_task()
        if not og.executor.paused:
            og.executor.pause()

    @staticmethod
    def open_install_folder():
        cwd = os.getcwd()
        subprocess.Popen(f'explorer "{cwd}"')

    @staticmethod
    def export_logs():
        app_name = og.config.get('gui_title')
        downloads_path = Path.home() / "Downloads"
        zip_path = downloads_path / f"{app_name}-log.zip"
        folders_to_archive = ["screenshots", "logs"]

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for folder in folders_to_archive:
                source_dir = Path.cwd() / folder
                if not source_dir.is_dir():
                    continue
                for file_path in source_dir.rglob("*"):
                    if file_path.is_file():
                        zipf.write(file_path, file_path.relative_to(Path.cwd()))

        subprocess.run(["explorer", f"/select,{zip_path}"])

    def update_task(self, task):
        self.update_status()

    def update_status(self):
        hotkey = self.basic_options.get('Start/Stop')
        suffix = f'({hotkey})' if hotkey and hotkey != 'None' else ''

        if og.executor.paused:
            device = og.device_manager.get_preferred_device()
            if device and not device['connected'] and device.get('full_path'):
                self.start_button.setText(self.tr("Start Game") + suffix)
            else:
                self.start_button.setText(self.tr("Start") + suffix)
            self.start_button.setIcon(FluentIcon.PLAY)
            self.status_bar.hide()
        else:
            self.start_button.setText(self.tr("Pause") + suffix)
            self.start_button.setIcon(FluentIcon.PAUSE)
            if not og.executor.connected():
                self.status_bar.setTitle(self.tr("Game Window Disconnected"))
                self.status_bar.setState(True)
            elif active_trigger_task_count := og.executor.active_trigger_task_count():
                if not og.executor.can_capture():
                    self.status_bar.setTitle(self.tr('Paused: PC Game Window Must Be in Front!'))
                    self.status_bar.setState(True)
                else:
                    self.status_bar.setTitle(
                        self.tr("Running") + ": " + str(active_trigger_task_count) + ' ' + self.tr("Trigger Tasks"))
                    self.status_bar.setState(False)
            elif task := og.executor.current_task:
                if not og.executor.can_capture():
                    self.status_bar.setTitle(self.tr('Paused: PC Game Window Must Be in Front!'))
                    self.status_bar.setState(True)
                elif task.enabled:
                    self.status_bar.setTitle(self.tr("Running") + ": " + task.name)
                    self.status_bar.setState(False)
                else:
                    self.status_bar.setTitle(self.tr("Waiting for task to be enabled"))
                    self.status_bar.setState(False)
            else:
                self.status_bar.setTitle(self.tr("Waiting for task to be enabled"))
                self.status_bar.setState(False)
            self.status_bar.show()

    def _is_key_held(self):
        """检查当前热键是否仍被按住"""
        if self._hotkey_vk:
            state = windll.user32.GetAsyncKeyState(self._hotkey_vk)
            return bool(state & 0x8000)
        return False

    def check_hotkey(self):
        new_hotkey = self.basic_options.get('Start/Stop')
        if new_hotkey != self.current_hotkey:
            self.rebind_hotkey(new_hotkey)
            self.current_hotkey = new_hotkey
            self.hotkey_changed.emit()

        # 长按检测：按住超过阈值则触发停止
        if self._hotkey_press_time > 0:
            if self._is_key_held():
                elapsed = time.time() - self._hotkey_press_time
                if elapsed >= self._long_press_threshold and not self._long_press_triggered:
                    self._long_press_triggered = True
                    self.long_pressed()
            else:
                # 按键已松开
                if not self._long_press_triggered:
                    # 短按：暂停/恢复
                    self.clicked()
                self._hotkey_press_time = 0
                self._long_press_triggered = False

        msg = wintypes.MSG()
        if windll.user32.PeekMessageW(byref(msg), None, 0, 0, 1):
            if msg.message == 0x0312:  # WM_HOTKEY
                logger.debug(f'hotkey pressed {msg}')
                if msg.wParam == 999:
                    self._hotkey_press_time = time.time()
                    self._long_press_triggered = False

        self.handler.post(self.check_hotkey, 0.1)

    def rebind_hotkey(self, hotkey):
        windll.user32.UnregisterHotKey(None, 999)
        vk_map = {'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B}

        if hotkey and hotkey != 'None' and hotkey in vk_map:
            self._hotkey_vk = vk_map[hotkey]
            if not windll.user32.RegisterHotKey(None, 999, 0, self._hotkey_vk):
                logger.error(f"Failed to register hotkey {hotkey}")
        else:
            self._hotkey_vk = 0
            logger.debug(f"Hotkey disabled or invalid: {hotkey}")
