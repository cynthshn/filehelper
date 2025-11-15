import ipaddress
import os
import socket
import _thread
import kivy.core.text

kivy.core.text.LabelBase.register(
          name='NotoSansCJK-Regular',
    fn_regular='NotoSansCJK-Regular.otf')

import kivy.clock
import kivy.lang
import kivy.properties
import kivy.uix.modalview
import kivy.utils
import kivy.uix.widget
import kivymd.app
import kivymd.uix.anchorlayout
import kivymd.uix.boxlayout
import kivymd.uix.button
import kivymd.uix.filemanager
import kivymd.uix.navigationbar
import kivymd.uix.screen
import kivy_garden.qrcode

import werkzeug.urls
if not hasattr(werkzeug.urls, 'url_quote'):
    import urllib.parse
    werkzeug.urls.url_quote = urllib.parse.quote

import http_server.server
import secrets
import waitress.server

if 'android' == kivy.utils.platform.lower():
    from android.storage import primary_external_storage_path
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.READ_EXTERNAL_STORAGE,
                         Permission.WRITE_EXTERNAL_STORAGE])
    external_storage_root = primary_external_storage_path()
else:
    external_storage_root = os.path.realpath(os.path.expanduser('~'))

class Application(kivymd.app.MDApp):

    def build(self):
        for key, style in self.theme_cls.font_styles.items():
            if key.lower() != 'icon':
                for _, fields in style.items():
                    fields['font-name'] = 'NotoSansCJK-Regular'
        if not ipaddr.is_private or ipaddr.is_loopback:
            return kivy.lang.Builder.load_string(KV_IP_ISNOT_PRIVATE)
        self.file_manager = kivymd.uix.filemanager.MDFileManager(
            exit_manager=self.exit_manager,
            select_path=self.select_path)
        with open('main.kv') as f:
            return kivy.lang.Builder.load_string(f.read())

    def on_switch_tabs(self, bar, item, item_icon, item_text):
        self.root.ids.screen_manager.current = item_text

    def file_manager_open(self):
        self.file_manager.show(external_storage_root)

    def select_path(self, path):
        kivy.clock.Clock.schedule_once(
            lambda dt: self._select_path(path), 0)

    def _select_path(self, path):
        self.exit_manager()
        if not path.startswith(FOLDER) or not os.path.exists(path):
            return
        filename = os.path.basename(path)
        data = app.url + path[len(FOLDER):]
        view = kivy.uix.modalview.ModalView(
            anchor_x='center', anchor_y='center')
        qr = kivy_garden.qrcode.QRCodeWidget(
                data=data, show_border=False,
                background_color=self.theme_cls.backgroundColor
            )
        layout = kivymd.uix.boxlayout.MDBoxLayout(
            kivymd.uix.anchorlayout.MDAnchorLayout(
                kivymd.uix.button.MDButton(
                    kivymd.uix.button.MDButtonText(text=filename),
                    style='text'
                ),
                anchor_x='center',
                anchor_y='bottom',
                size_hint_y=.2
            ),
            kivymd.uix.boxlayout.MDBoxLayout(
                kivy.uix.widget.Widget(size_hint_x=.2), qr,
                kivy.uix.widget.Widget(size_hint_x=.2)
            ),
            kivy.uix.widget.Widget(size_hint_y=.05),
            kivymd.uix.anchorlayout.MDAnchorLayout(
                kivymd.uix.button.MDButton(
                    kivymd.uix.button.MDButtonText(text='退出'),
                    style='filled',
                    on_press=view.dismiss
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

    def exit_manager(self, *args):
        self.file_manager.close()

KV_IP_ISNOT_PRIVATE = '''\
MDBoxLayout:
    size_hint: 1., 1.
    md_bg_color: self.theme_cls.backgroundColor
    orientation: 'vertical'

    MDAnchorLayout:
        anchor_x: 'center'
        anchor_y: 'center'

        MDButton:
            style: 'text'

            MDButtonText:
                text: 'WIFI未连接，请连接后重新打开程序。'

    MDAnchorLayout:
        anchor_x: 'center'
        anchor_y: 'center'

        MDButton:
            style: 'elevated'
            on_press: app.stop()

            MDButtonText:
                text: '退出'
'''

class BaseScreen(kivymd.uix.screen.MDScreen):

    ...

class BaseMDNavigationItem(kivymd.uix.navigationbar.MDNavigationItem):

    icon = kivy.properties.StringProperty()
    text = kivy.properties.StringProperty()

def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('114.114.114.114', 53))
        return s.getsockname()[0]

if '__main__' == __name__:
    app = Application()
    ip = get_local_ip()
    ipaddr = ipaddress.ip_address(ip)
    http_server.server.app.secret_key = str(secrets.token_hex())
    if external_storage_root.endswith('/'):
        FOLDER = external_storage_root
    else:
        FOLDER = external_storage_root + '/'
    http_server.server.app.config['FOLDER'] = FOLDER
    server = waitress.server.create_server(
                 http_server.server.app, host=ip, port=0
             )
    port = server.socket.getsockname()[1]
    _thread.start_new_thread(server.run, ())
    app.url = f'http://{ip}:{port}/'
    app.run()
