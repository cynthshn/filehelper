import binascii
import marshal
import os
import select
import socket
import socketserver
import SimpleHTTPServerWithUpload
import _thread
#from kivy.core.text import LabelBase
#LabelBase.register(
#          name='NotoSansCJK-Regular',
#    fn_regular='NotoSansCJK-Regular.otf')
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import StringProperty
from kivy.uix.modalview import ModalView
from kivy.utils import platform
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.anchorlayout import MDAnchorLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
    MDDialogContentContainer
)
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.label import MDLabel
from kivymd.uix.navigationbar import MDNavigationBar, MDNavigationItem
from kivymd.uix.screen import MDScreen
from kivy_garden.qrcode import QRCodeWidget
from kivy_garden.zbarcam import ZBarCam
from pyzbar.pyzbar import ZBarSymbol

if 'android' == platform.lower():
    from android.storage import primary_external_storage_path
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.READ_EXTERNAL_STORAGE,
                         Permission.WRITE_EXTERNAL_STORAGE])
    external_storage_root = primary_external_storage_path()
    downloads = os.path.join(external_storage_root, 'Download')
    if not os.path.exists(downloads):
        os.makedirs(downloads, exist_ok=True)
else:
    external_storage_root = os.path.abspath(os.path.expanduser('~'))
    downloads = os.path.join(external_storage_root, 'Downloads')
    if not os.path.exists(downloads):
        os.makedirs(downloads, exist_ok=True)
with open('main.kv') as f:
    KV = f.read()
os.chdir(downloads)

class Demo(MDApp):

    def build(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        s.close()
        server = socketserver.TCPServer(
            (ip, 0),
            SimpleHTTPServerWithUpload.SimpleHTTPRequestHandler)
        port = server.socket.getsockname()[1]
        self.url = f'http://{ip}:{port}/'
        _thread.start_new_thread(server.serve_forever, ())
        #for key, style in self.theme_cls.font_styles.items():
        #    if key.lower() in (
        #       'icon').split(): # display headline title').split():
        #        continue
        #    for _, fields in style.items():
        #        fields['font-name'] = 'NotoSansCJK-Regular'
        self.file_manager = MDFileManager(
                            exit_manager=self.exit_manager,
                            select_path=self.select_path)
        return Builder.load_string(KV)

    def on_switch_tabs(self, bar, item, item_icon, item_text):
        self.root.ids.screen_manager.current = item_text

    def scan_qrcode(self):
        view = ScanView()
        def dismiss(*args, **kwrags):
            zbarcam = view.ids.zbarcam
            camera = getattr(zbarcam.xcamera, '_camera', None)
            zbarcam.stop()
            if camera:
                camera.stop()
                device = getattr(camera, '_device', None)
                if device:
                    device.release()
            view.dismiss()
        view.ids.zbarcam.bind(symbols=
             lambda _, symbols: self.on_symbols(symbols, dismiss))
        view.ids.exit_btn.bind(on_press=dismiss)
        view.open()

    def on_symbols(self, symbols, dismiss):
        for symbol in symbols:
            if b'file:' != symbol.data[:5]:
                continue
            ip, port, token, filename = marshal.loads(
                             binascii.a2b_base64(symbol.data[5:]))
            dismiss()
            dialog = MDDialog(
                MDDialogIcon(icon='download-circle-outline',),
                MDDialogHeadlineText(text='Downloading ...'),
                MDDialogSupportingText(text=
                   'The file is downloading, do not close this app')
            )
            dialog.open()
            context = RecvContext(ip, port, token, filename, dialog)
            _thread.start_new_thread(context.recv_file, ())
            break

    def file_manager_open(self):
        self.file_manager.show(downloads)

    def select_path(self, path):
        Clock.schedule_once(lambda dt: self._select_path(path), 0)

    def _select_path(self, path):
        self.exit_manager()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        s.close()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, 0))
        port = server.getsockname()[1]
        token = os.urandom(8)
        context = {'running': 0, 'token': token,
                   'path': path, 'server': server}
        filename = os.path.basename(path)
        data = 'file:' + binascii.b2a_base64(
             marshal.dumps((ip, port, token, filename))).decode().strip()
        view = ModalView(anchor_x='center', anchor_y='center')
        qr = QRCodeWidget(data=data, show_border=False,
             background_color=self.theme_cls.backgroundColor)
        def dismiss(*args, **kwrags):
            context['running'] = 0
            view.dismiss()
        layout = MDBoxLayout(
            MDAnchorLayout(
                MDButton(
                    MDButtonText(text=filename),
                    style='text'
                ),
                anchor_x='center',
                anchor_y='bottom',
                size_hint_y=.2
            ),
            MDBoxLayout(
                Widget(size_hint_x=.2), qr, Widget(size_hint_x=.2)
            ),
            Widget(size_hint_y=.05),
            MDAnchorLayout(
                MDButton(
                    MDButtonText(text='Exit'),
                    style='filled',
                    on_press=dismiss
                ),
                anchor_x='center',
                anchor_y='top',
                size_hint_y=.2
            ),
            size_hint=(1., 1.),
            md_bg_color=self.theme_cls.backgroundColor,
            orientation='vertical'
        )
        view.add_widget(layout)
        view.open()
        server.listen(8)
        context['running'] = 1
        _thread.start_new_thread(self.serve_forever, (context, ))

    def exit_manager(self, *args):
        self.file_manager.close()

    def serve_forever(self, context):
        server = context['server']
        path = context['path']
        def sendfile(conn):
            f_out = conn.makefile('rwb')
            if f_out.read(8) != context['token']:
                return
            fn = os.path.abspath(path)
            with open(fn, 'rb') as f_in:
                data = f_in.read(8192)
                while data:
                    f_out.write(data)
                    data = f_in.read(8192)
            f_out.flush()
            f_out.close()
            conn.close()
        while context['running']:
            r, _, _ = select.select([server.fileno()], [], [], .5)
            if not r:
                continue
            conn, addr = server.accept()
            _thread.start_new_thread(sendfile, (conn, ))

class RecvContext:

    def __init__(self, ip, port, token, filename, dialog):
        self.ip = ip
        self.port = port
        self.token = token
        self.filename = filename
        self.dialog = dialog
        self.running = 1

    def recv_file(self):
        ip = self.ip
        port = self.port
        token = self.token
        filename = self.filename
        dialog = self.dialog
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((ip, port))
            f_in = conn.makefile('rwb')
            path = os.path.join(downloads, filename)
            with open(path, 'wb') as f_out:
                f_in.write(token)
                f_in.flush()
                data = f_in.read(8192)
                while data:
                    f_out.write(data)
                    data = f_in.read(8192)
            f_in.close()
            conn.close()
        finally:
            Clock.schedule_once(lambda dt: dialog.dismiss(), 0)

class BaseScreen(MDScreen): ...
class BaseMDNavigationItem(MDNavigationItem):
    icon = StringProperty()
    text = StringProperty()
class ScanView(ModalView): ...

if '__main__' == __name__:
    Demo().run()
