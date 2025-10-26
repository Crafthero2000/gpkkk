import sys
import csv
from datetime import datetime
import asyncio
import qasync
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QTabWidget, QFormLayout, QInputDialog
)
from PyQt6.QtGui import QTextCursor, QColor
from mx10 import MX10  # новая библиотека

PRINTER_ADDRESS = "A1:11:02:23:64:0D"  # твой адрес

class AdminWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MX10 Admin Panel")
        self.resize(600, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ===== Подключение =====
        top = QHBoxLayout()
        self.btn_connect = QPushButton("Подключиться")
        self.btn_connect.clicked.connect(lambda: asyncio.create_task(self.connect_printer()))
        self.btn_disconnect = QPushButton("Отключиться")
        self.btn_disconnect.clicked.connect(lambda: asyncio.create_task(self.disconnect_printer()))
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)
        layout.addLayout(top)

        self.status_label = QLabel("Статус: ❌ Отключено")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        layout.addWidget(self.status_label)

        # ===== Вкладки =====
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---- Вкладка команд ----
        self.tab_cmds = QWidget()
        tab_layout = QVBoxLayout(self.tab_cmds)

        btn_feed = QPushButton("Подать бумагу")
        btn_feed.clicked.connect(lambda: asyncio.create_task(self.feed_paper()))
        btn_retract = QPushButton("Втянуть бумагу")
        btn_retract.clicked.connect(lambda: asyncio.create_task(self.retract_paper()))
        btn_print_text = QPushButton("Печать текста")
        btn_print_text.clicked.connect(lambda: asyncio.create_task(self.print_text()))
        btn_get_info = QPushButton("Получить инфо о принтере")
        btn_get_info.clicked.connect(lambda: asyncio.create_task(self.get_info()))
        btn_monitor = QPushButton("Мониторинг статуса (30 сек)")
        btn_monitor.clicked.connect(lambda: asyncio.create_task(self.monitor_status()))
        tab_layout.addWidget(btn_get_info)
        tab_layout.addWidget(btn_feed)
        tab_layout.addWidget(btn_retract)
        tab_layout.addWidget(btn_print_text)
        tab_layout.addWidget(btn_monitor)

        self.tabs.addTab(self.tab_cmds, "Команды")

        # ---- Вкладка произвольной команды ----
        self.tab_custom = QWidget()
        custom_layout = QFormLayout(self.tab_custom)
        self.input_cmd = QLineEdit()
        self.input_payload = QLineEdit()
        self.btn_send_custom = QPushButton("Отправить")
        self.btn_send_custom.clicked.connect(lambda: asyncio.create_task(self.send_custom_command()))
        custom_layout.addRow("CMD (hex):", self.input_cmd)
        custom_layout.addRow("Payload (hex):", self.input_payload)
        custom_layout.addWidget(self.btn_send_custom)
        self.tabs.addTab(self.tab_custom, "Произвольная команда")

        # ---- Вкладка лог ----
        self.tab_log = QWidget()
        log_layout = QVBoxLayout(self.tab_log)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background-color: #1e1e1e; color: white; font-family: Consolas; font-size: 13px;")
        log_layout.addWidget(self.log)
        self.tabs.addTab(self.tab_log, "Лог")

        # Статусы
        self.info_label = QLabel("Батарея: —   Бумага: —   Температура: —")
        layout.addWidget(self.info_label)

        self.printer: MX10 | None = None

    # ===== Логирование =====
    def log_msg(self, text: str, color: str = "white"):
        self.log.setTextColor(QColor(color))
        self.log.append(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    # ===== Подключение/отключение =====
    async def connect_printer(self):
        try:
            self.log_msg("🔍 Подключение к принтеру...", "yellow")
            self.printer = MX10(PRINTER_ADDRESS)
            self.printer.status_callback = self.handle_status
            await self.printer.connect()
            self.status_label.setText("Статус: ✅ Подключено")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            self.log_msg("✅ Принтер подключен", "green")
            await self.printer.get_status()  # первый опрос
        except Exception as e:
            self.log_msg(f"❌ Ошибка подключения: {e}", "red")
            self.printer = None

    async def get_info(self):
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        await self.printer.get_info()
        self.log_msg("📤 Запрос информации отправлен", "#90EE90")

    async def monitor_status(self):
        """Мониторинг статуса в течение 30 секунд"""
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        
        self.log_msg("🔍 Мониторинг начат (каждые 2 секунды)...", "yellow")
        
        try:
            for i in range(15):  # 15 раз × 2 сек = 30 секунд
                await self.printer.get_status()
                self.log_msg(f"⏱ Запрос {i+1}/15", "gray")
                await asyncio.sleep(2)
            
            self.log_msg("✅ Мониторинг завершён", "green")
        except Exception as e:
            self.log_msg(f"❌ Ошибка мониторинга: {e}", "red")

    def log_status_csv(self, byte0, byte1, byte2):
        """Сохраняет статус в CSV"""
        filename = "printer_status_log.csv"
        header = ["timestamp", "byte0", "byte1", "byte2"]
        row = [datetime.now().isoformat(), byte0, byte1, byte2]

        # Проверяем, есть ли файл — если нет, создаём и пишем заголовок
        try:
            with open(filename, "r", newline="") as f:
                pass
        except FileNotFoundError:
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)

        # Добавляем новую строку
        with open(filename, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    async def disconnect_printer(self):
        if self.printer:
            await self.printer.disconnect()
            self.printer = None
            self.status_label.setText("Статус: ❌ Отключено")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.log_msg("🔌 Принтер отключен", "gray")

    # ===== Обработка статусов =====
    def handle_status(self, data: bytearray):
        hex_data = " ".join(f"{b:02X}" for b in data)
        self.log_msg(f"📥 RX: {hex_data}", "#87CEEB")
        
        if len(data) < 11:
            self.log_msg(f"⚠ Короткий пакет: {len(data)} байт", "orange")
            return
        
        # Проверка заголовка
        if data[0] != 0x51 or data[1] != 0x78:
            self.log_msg(f"⚠ Неверный заголовок", "orange")
            return
        
        cmd = data[2]
        type_byte = data[3]
        payload_len = data[4] | (data[5] << 8)  # Little-endian
        
        self.log_msg(f"CMD: 0x{cmd:02X}, Type: 0x{type_byte:02X}, Payload len: {payload_len}", "gray")
        
        # Парсим статус (CMD = 0xA3)
        if cmd == 0xA3:
            # Извлекаем payload (3 байта в твоём случае)
            payload_start = 6
            payload_end = 6 + payload_len
            
            if len(data) < payload_end + 2:  # +2 для CRC и 0xFF
                self.log_msg(f"⚠ Неполный пакет", "orange")
                return
            
            payload = data[payload_start:payload_end]
            crc_received = data[payload_end]
            end_marker = data[payload_end + 1]
            
            # Проверяем CRC
            from mx10 import crc8
            crc_calculated = crc8(payload)
            crc_valid = crc_calculated == crc_received
            
            self.log_msg(
                f"Payload: {' '.join(f'{b:02X}' for b in payload)} | "
                f"CRC: {'✅' if crc_valid else '❌'} (calc=0x{crc_calculated:02X}, recv=0x{crc_received:02X}) | "
                f"End: 0x{end_marker:02X}",
                "green" if crc_valid else "orange"
            )
            
            # Парсим 3 байта payload
            if payload_len >= 3:
                byte0 = payload[0]
                byte1 = payload[1]
                byte2 = payload[2]

                # Сохраняем в CSV
                self.log_status_csv(byte0, byte1, byte2)

                # Статус бумаги
                paper_ok = (byte0 & 0x01) == 1
                self.info_label.setText(
                    f"📄 Бумага: {'✅ OK' if paper_ok else '❌ Нет'}  "
                    f"❓ Byte1: {byte1}  "
                    f"❓ Byte2: {byte2} (0x{byte2:02X})"
                )
                
                # Обновляем UI
                self.info_label.setText(
                    f"📄 Бумага: {'✅ OK' if paper_ok else '❌ Нет'}  "
                    f"❓ Byte1: {byte1}  "
                    f"❓ Byte2: {byte2} (0x{byte2:02X})"
                )

    # ===== Команды ----
    async def feed_paper(self):
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        await self.printer.feed(0x20)
        self.log_msg("📤 Подан лист бумаги", "#90EE90")
        await self.printer.get_status()

    async def retract_paper(self):
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        await self.printer.retract(0x20)
        self.log_msg("📤 Бумага втянута", "#90EE90")
        await self.printer.get_status()

    async def print_text(self):
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        text, ok = QInputDialog.getText(self, "Печать текста", "Введите текст:")
        if ok and text:
            rows = self.text_to_bitmap(text)  # обычные байты
            await self.printer.print_bitmap(rows)  # библиотека сама применит reverse_bits
            self.log_msg(f"🖨 Печать текста: {text}", "#ADD8E6")
            await self.printer.get_status()

    # ===== Произвольная команда ----
    async def send_custom_command(self):
        if not self.printer:
            return self.log_msg("⚠ Принтер не подключен", "orange")
        try:
            cmd = int(self.input_cmd.text(), 16)
            payload_hex = self.input_payload.text().replace(" ", "")
            payload = bytes.fromhex(payload_hex) if payload_hex else b""
            await self.printer.send_raw(cmd, payload)  # метод нужно добавить в библиотеку
            self.log_msg(f"📤 Отправлена команда {cmd:02X} с payload {payload.hex()}", "#FFD700")
            await self.printer.get_status()
        except Exception as e:
            self.log_msg(f"❌ Ошибка отправки команды: {e}", "red")

    # ===== Вспомогательные =====
    def text_to_bitmap(self, text: str, width=384) -> list[bytes]:
        from PIL import Image, ImageOps, ImageDraw, ImageFont

        width = int(width)  # <-- важный момент, если вдруг будет строка

        img = Image.new('L', (width, 60), color=255)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()

        draw.text((0, 0), text, font=font, fill=0)
        img = ImageOps.grayscale(img)
        img = img.convert('1')

        w, h = img.size
        rows = []

        for y in range(h):
            row_bytes = bytearray()
            for x in range(0, w, 8):
                byte = 0
                for bit in range(8):
                    px = x + bit
                    if px < w:
                        pixel = img.getpixel((px, y))
                        black = 1 if pixel == 0 else 0
                        byte |= (black << (7 - bit))  # переворачиваем биты для печати слева направо
                row_bytes.append(byte)
            rows.append(bytes(row_bytes))
        return rows


# ===== Запуск =====
if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    w = AdminWindow()
    w.show()

    with loop:
        loop.run_forever()
