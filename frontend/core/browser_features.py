"""Window ke features: fullscreen video, find in page, print / PDF.
MainWindow mein sirf BrowserFeatures banao aur har naye tab pe attach_view() call karo."""

import re
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from frontend.core.settings_manager import settings
from frontend.widgets.hover_status import HoverStatus
from frontend.widgets.site_settings import SiteSettingsDialog
from frontend.widgets.tab_search import TabSearch
from frontend.widgets.web_view import display_url


class BrowserFeatures:
    def __init__(self, window, find_bar, chrome_widgets: list):
        """chrome_widgets = wo widgets jo fullscreen mein chhup jate hain (tab bar, address bar, sidebar...)."""
        self.w = window
        self.find_bar = find_bar
        self._chrome = chrome_widgets
        self._hidden_before: list = []
        self._fs_view = None
        self._was_maximized = False
        self._printer = None
        self._pins_ready = False

        self.find_bar.find_requested.connect(self._find)
        self.find_bar.closed.connect(self._clear_find)

        self.hover = HoverStatus(window.pages)
        window.tab_strip.context_requested.connect(self._tab_menu)
        # tab band ho to pinned list dobara save (widgetRemoved ke baad tab bar bhi update ho chuka hota hai)
        window.stack.widgetRemoved.connect(lambda _i: QTimer.singleShot(0, self.save_pins))

    # ---------- har tab ke liye ----------
    def attach_view(self, view) -> None:
        view.fullscreen_changed.connect(lambda on, v=view: self._on_fullscreen(v, on))
        view.print_requested.connect(lambda v=view: self.print_page(v))
        view.printFinished.connect(self._on_print_finished)
        view.link_hovered.connect(lambda url, v=view: self._on_hover(v, url))
        page = view.page()
        page.pdfPrintingFinished.connect(self._on_pdf_finished)
        page.find_result.connect(lambda active, total, v=view: self._on_find_result(v, active, total))

    def install_shortcuts(self) -> None:
        def key(seq: str, fn) -> QShortcut:
            return QShortcut(QKeySequence(seq), self.w, activated=fn)

        key("Ctrl+F", self.open_find)
        key("F3", lambda: self._step(True))
        key("Shift+F3", lambda: self._step(False))
        key("Ctrl+P", lambda: self.print_page())
        key("Ctrl+Shift+P", lambda: self.save_pdf())
        key("Ctrl+Shift+A", self.open_tab_search)
        key("Ctrl+Alt+S", lambda: self.open_site_settings())
        # Esc sirf fullscreen mein active hota hai, warna websites ka Esc chheen leta
        self._esc = key("Esc", self._exit_fullscreen)
        self._esc.setEnabled(False)

    def on_tab_changed(self) -> None:
        """Tab badle to fullscreen, find bar aur hover URL band karo."""
        self.hover.hide()
        if self._fs_view is not None and self._fs_view is not self.w.current_view:
            self._exit_fullscreen()
        if self.find_bar.isVisible():
            self.find_bar.close_bar()

    # ---------- tab search / site settings ----------
    def open_tab_search(self) -> None:
        stack = self.w.stack
        entries = []
        for i in range(stack.count()):
            view = stack.widget(i)
            entries.append((i, view.title() or "New Tab", display_url(view.url().toString())))
        index = TabSearch(entries, self.w).show_centered(self.w)
        if index >= 0:
            self.w._show_browser()
            self.w.tab_strip.set_current(index)

    def open_site_settings(self, view=None) -> None:
        view = view or self.w.current_view
        host = view.site_key() if view is not None else ""
        if not host:
            self.w.statusBar().showMessage("Site settings sirf websites (http/https) ke liye hain", 3000)
            return
        SiteSettingsDialog(host, self.w).exec()

    # ---------- fullscreen ----------
    def _on_fullscreen(self, view, on: bool) -> None:
        w = self.w
        if on and self._fs_view is None:
            self._fs_view = view
            self._was_maximized = w.isMaximized()
            self._hidden_before = [x for x in self._chrome if x.isHidden()]
            for x in self._chrome:
                x.hide()
            self.find_bar.hide()
            w.showFullScreen()
            self._esc.setEnabled(True)
        elif not on and self._fs_view is not None:
            self._fs_view = None
            for x in self._chrome:
                if x not in self._hidden_before:
                    x.show()
            self._esc.setEnabled(False)
            w.showMaximized() if self._was_maximized else w.showNormal()

    def _exit_fullscreen(self) -> None:
        view = self._fs_view
        if view is not None:
            view.page().triggerAction(QWebEnginePage.WebAction.ExitFullScreen)
            self._on_fullscreen(view, False)  # page ka jawab na aaye tab bhi window wapas aaye

    # ---------- find in page ----------
    def open_find(self) -> None:
        if self.w.current_view is None:
            return
        self.w._show_browser()
        preset = (self.w.current_view.selectedText() or "").strip()
        self.find_bar.open_bar(preset[:80] if "\n" not in preset else "")

    def _find(self, text: str, forward: bool, case: bool) -> None:
        view = self.w.current_view
        if view is not None:
            view.find(text, forward, case)

    def _step(self, forward: bool) -> None:
        if self.find_bar.isVisible():
            self._find(self.find_bar.input.text(), forward, self.find_bar.case_btn.isChecked())

    def _clear_find(self) -> None:
        view = self.w.current_view
        if view is not None:
            view.clear_find()

    def _on_find_result(self, view, active: int, total: int) -> None:
        if view is self.w.current_view:
            self.find_bar.set_result(active, total)

    # ---------- print / PDF ----------
    def print_page(self, view=None) -> None:
        view = view or self.w.current_view
        if view is None:
            return
        try:
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
        except ImportError:
            QMessageBox.warning(self.w, "Print", "Print support install nahi hai. 'Save as PDF' (Ctrl+Shift+P) use karo.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self.w)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._printer = printer  # print hone tak zinda rakho
            view.print(printer)

    def _on_print_finished(self, ok: bool) -> None:
        self._printer = None
        if not ok:
            QMessageBox.warning(self.w, "Print", "Print nahi ho saka.")

    def save_pdf(self, view=None) -> None:
        view = view or self.w.current_view
        if view is None:
            return
        name = re.sub(r"[^\w\- ]+", "", view.title() or "page").strip()[:60] or "page"
        start = str(Path(settings.get("download_dir")) / f"{name}.pdf")
        path, _ = QFileDialog.getSaveFileName(self.w, "Save as PDF", start, "PDF (*.pdf)")
        if path:
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            view.page().printToPdf(path)

    def _on_pdf_finished(self, path: str, ok: bool) -> None:
        if ok:
            QMessageBox.information(self.w, "Save as PDF", f"PDF save ho gaya:\n{path}")
        else:
            QMessageBox.warning(self.w, "Save as PDF", "PDF save nahi ho saka.")

    # ---------- link hover ----------
    def _on_hover(self, view, url: str) -> None:
        if view is self.w.current_view and self._fs_view is None:
            self.hover.show_url(url)

    # ---------- window ko samne lao / URLs kholo (dusri process ya default browser se) ----------
    def open_urls(self, urls: list) -> None:
        for url in urls:
            self.w.add_tab(url=url)
        if urls:
            self.w._show_browser()
        if self.w.isMinimized():
            self.w.showNormal()
        self.w.raise_()
        self.w.activateWindow()

    # ---------- pinned tabs ----------
    def restore_pins(self) -> None:
        """Startup ke baad ek dafa call karo: pehle se khuli tab pin ho jati hai, warna nayi khulti hai."""
        if self._pins_ready:
            return
        if self.w._is_first:
            for url in list(settings.get("pinned_tabs") or []):
                view = next((v for v in self.w._views() if v.url().toString() == url), None)
                if view is None:
                    view = self.w.add_tab(url=url, activate=False)
                self._set_pinned(view, True)
        self._pins_ready = True
        self.save_pins()

    def _set_pinned(self, view, pinned: bool) -> None:
        strip, stack = self.w.tab_strip, self.w.stack
        index = stack.indexOf(view)
        if index < 0 or strip.is_pinned(index) == pinned:
            return
        count = sum(1 for i in range(strip.count()) if strip.is_pinned(i))
        target = count if pinned else count - 1  # pinned tabs hamesha sab se left

        current = stack.currentWidget()
        strip.bar.blockSignals(True)
        stack.blockSignals(True)
        strip.set_pinned(index, pinned)
        if target != index:
            strip.move_tab(index, target)
            stack.removeWidget(view)
            stack.insertWidget(target, view)
        stack.setCurrentWidget(current)
        strip.bar.setCurrentIndex(stack.indexOf(current))
        stack.blockSignals(False)
        strip.bar.blockSignals(False)
        self.save_pins()

    def save_pins(self) -> None:
        if not self._pins_ready or not self.w._is_first:
            return
        strip, stack = self.w.tab_strip, self.w.stack
        urls = []
        for i in range(strip.count()):
            if strip.is_pinned(i):
                url = stack.widget(i).url().toString()
                if url.startswith(("http://", "https://")):
                    urls.append(url)
        settings.set("pinned_tabs", urls)

    # ---------- tab ka right-click menu ----------
    def _tab_menu(self, index: int, global_pos) -> None:
        stack, strip = self.w.stack, self.w.tab_strip
        view = stack.widget(index)
        if view is None:
            return
        pinned = strip.is_pinned(index)
        page = view.page()
        muted = page.isAudioMuted()

        menu = QMenu(self.w)
        menu.addAction("Unpin tab" if pinned else "Pin tab", lambda: self._set_pinned(view, not pinned))
        menu.addAction("Reload", lambda: view.reload())
        menu.addAction("Duplicate tab", lambda: self.w.add_tab(url=view.url().toString()))
        menu.addAction("Unmute tab" if muted else "Mute tab", lambda: page.setAudioMuted(not muted))
        menu.addAction("Site settings...", lambda: self.open_site_settings(view))
        menu.addSeparator()
        menu.addAction("Close tab", lambda: self.w.close_tab(stack.indexOf(view)))
        menu.addAction("Close other tabs", lambda: self._close_others(view))
        menu.exec(global_pos)

    def _close_others(self, keep) -> None:
        stack, strip = self.w.stack, self.w.tab_strip
        for i in reversed(range(stack.count())):
            view = stack.widget(i)
            if view is not keep and not strip.is_pinned(i):
                self.w.close_tab(i)