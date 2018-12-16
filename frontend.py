import sys, gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, WebKit2

class Frontend(Gtk.Window):
    def __init__(self, geometry=None):
        Gtk.init(sys.argv)
        super().__init__()
        self.set_title('DOS Games')
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._key_pressed)

        self.webview = WebKit2.WebView()
        self.webview.connect('context-menu', self._context_menu)
        self.webview.set_background_color(Gdk.RGBA(0,0,0,1))
        self.webview.load_uri('http://localhost:11236/')
        self.webview.get_settings().set_enable_write_console_messages_to_stdout(True)
        self.add(self.webview)
        self.webview.show()

        if geometry:
            self.parse_geometry(geometry)
            self.set_resizable(False)

        self.show()

    def _context_menu(self, webview, context_menu, event, hit_test_result):
        return True

    def start(self):
        Gtk.main()

    def end(self):
        self.destroy()
        Gtk.main_quit()

    def console_message(self, *args, **kwargs):
        print(args, kwargs)

    def _key_pressed(self, widget, event):
        modifiers = Gtk.accelerator_get_default_mod_mask()
        if event.keyval == Gdk.KEY_Escape:
            self.end()
        if event.state & modifiers == Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_r:
                self.webview.reload()
            if event.keyval == Gdk.KEY_q:
                self.end()
            if event.keyval == Gdk.KEY_w:
                self.end()
