"""wxPython dialog for selecting nets in KiCad plugin.

Only imported when running inside KiCad's Python environment,
which bundles wxPython.
"""

from __future__ import annotations

import wx


class NetSelectorDialog(wx.Dialog):
    """Multi-select list dialog for board nets."""

    def __init__(self, parent, nets: list[str], title: str = "Select Nets to Expose"):
        super().__init__(parent, title=title, size=(400, 500))
        self._nets = sorted(set(nets))
        self._selected: list[str] = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Filter text
        self._filter = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self._filter.SetHint("Filter nets...")
        self._filter.Bind(wx.EVT_TEXT, self._on_filter)
        sizer.Add(self._filter, 0, wx.EXPAND | wx.ALL, 5)

        # Check list box
        self._listbox = wx.CheckListBox(panel, choices=self._nets)
        sizer.Add(self._listbox, 1, wx.EXPAND | wx.ALL, 5)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_all = wx.Button(panel, label="Select All")
        btn_none = wx.Button(panel, label="Select None")
        btn_ok = wx.Button(panel, wx.ID_OK, label="OK")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_all.Bind(wx.EVT_BUTTON, self._on_select_all)
        btn_none.Bind(wx.EVT_BUTTON, self._on_select_none)
        btn_sizer.Add(btn_all, 0, wx.ALL, 5)
        btn_sizer.Add(btn_none, 0, wx.ALL, 5)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(btn_ok, 0, wx.ALL, 5)
        btn_sizer.Add(btn_cancel, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.CentreOnParent()

    def _on_filter(self, event: wx.Event) -> None:
        text = self._filter.GetValue().lower()
        filtered = [n for n in self._nets if text in n.lower()]
        checked = {self._listbox.GetString(i) for i in self._listbox.GetCheckedItems()}
        self._listbox.Set(filtered)
        for i, name in enumerate(filtered):
            if name in checked:
                self._listbox.Check(i)

    def _on_select_all(self, event: wx.Event) -> None:
        for i in range(self._listbox.GetCount()):
            self._listbox.Check(i)

    def _on_select_none(self, event: wx.Event) -> None:
        for i in range(self._listbox.GetCount()):
            self._listbox.Check(i, False)

    def ShowModal(self) -> int:
        result = super().ShowModal()
        if result == wx.ID_OK:
            self._selected = [
                self._listbox.GetString(i)
                for i in self._listbox.GetCheckedItems()
            ]
        return result

    @property
    def selected(self) -> list[str]:
        return self._selected
