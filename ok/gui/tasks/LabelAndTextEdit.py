from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import TextEdit, PushButton, FluentIcon

from ok.gui.tasks.ConfigLabelAndWidget import ConfigLabelAndWidget


class LabelAndTextEdit(ConfigLabelAndWidget):

    def __init__(self, config_desc, config, key: str, height=None, save_callback=None):
        super().__init__(config_desc, config, key)
        self.key = key

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        self.text_edit = TextEdit()
        if height:
            self.text_edit.setFixedHeight(height)
        else:
            font = self.text_edit.font()
            font_metrics = QFontMetrics(font)
            row_height = font_metrics.lineSpacing()
            self.text_edit.setFixedHeight(row_height * 6)
        self.update_value()
        self.text_edit.textChanged.connect(self.value_changed)
        container_layout.addWidget(self.text_edit)

        if save_callback:
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            save_btn = PushButton(FluentIcon.SAVE, "保存")
            save_btn.clicked.connect(lambda: save_callback(self.text_edit.toPlainText()))
            btn_layout.addWidget(save_btn)
            container_layout.addLayout(btn_layout)

        self.add_widget(container)

    def update_value(self):
        self.text_edit.setText(self.config.get(self.key))

    def value_changed(self):
        self.update_config(self.text_edit.toPlainText())
