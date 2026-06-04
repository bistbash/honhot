"""Weekly timetable grid that accepts entity drops."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from app.config import DAYS, ENTITY_MIME_TYPE, HOURS
from app.controllers.schedule_controller import SlotInfo

_ALLOWED_BRUSH = QColor(46, 174, 110, 60)
_BLOCKED_BRUSH = QColor(120, 120, 120, 35)
_UNAVAILABLE_BRUSH = QColor(214, 69, 69, 90)
_GLOBAL_BRUSH = QColor(232, 150, 40, 110)


def _subject_color(name: str) -> QColor:
    """Return a stable, soft background color derived from the subject name."""
    hue = (hash(name) % 360 + 360) % 360
    color = QColor.fromHsl(hue, 150, 210)
    color.setAlpha(150)
    return color


class TimetableGrid(QTableWidget):
    """A days x hours grid; cells are drop targets for entities."""

    entityDropped = Signal(int, int, str, int)  # day, hour, entity_type, entity_id
    unassignRequested = Signal(int, int)  # day, hour
    moveRequested = Signal(int, int, int, int)  # src_day, src_hour, dst_day, dst_hour

    def __init__(self, parent=None) -> None:
        super().__init__(len(HOURS), len(DAYS), parent)
        self.setHorizontalHeaderLabels(DAYS)
        self.setVerticalHeaderLabels([f"שעה {h}" for h in HOURS])
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setWordWrap(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._hour_to_row = {hour: r for r, hour in enumerate(HOURS)}
        self._unavailable: set[tuple[int, int]] = set()
        self._global_blocked: set[tuple[int, int]] = set()
        self._slots: dict[tuple[int, int], SlotInfo] = {}
        self._move_source: tuple[int, int] | None = None
        self._build_cells()

    # ------------------------------------------------------------------ cells
    def _build_cells(self) -> None:
        for r in range(len(HOURS)):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, c, item)

    def populate(
        self,
        slots: dict[tuple[int, int], SlotInfo],
        unavailable: set[tuple[int, int]] | None = None,
        global_blocked: set[tuple[int, int]] | None = None,
    ) -> None:
        """Fill the grid from a {(day, hour): SlotInfo} mapping.

        ``unavailable`` cells (where this tutor cannot teach) are tinted red,
        and ``global_blocked`` cells (school-wide breaks affecting everyone) are
        tinted orange, so the user immediately sees the recurring constraints.
        """
        self._unavailable = set(unavailable or set())
        self._global_blocked = set(global_blocked or set())
        self._slots = dict(slots)
        for r, hour in enumerate(HOURS):
            for c in range(len(DAYS)):
                item = self.item(r, c)
                if item is None:
                    continue
                slot = slots.get((c, hour))
                if slot is not None:
                    item.setText(slot.label)
                    item.setBackground(QBrush(_subject_color(slot.subject_name)))
                elif (c, hour) in self._global_blocked:
                    item.setText("✗ הפסקה")
                    item.setBackground(QBrush(_GLOBAL_BRUSH))
                elif (c, hour) in self._unavailable:
                    item.setText("✗ אילוץ")
                    item.setBackground(QBrush(_UNAVAILABLE_BRUSH))
                else:
                    item.setText("")
                    item.setBackground(QBrush(Qt.GlobalColor.transparent))

    def highlight_allowed(self, allowed: set[tuple[int, int]] | None) -> None:
        """Tint cells to indicate where the selected entity may be dropped.

        ``allowed`` is a set of (day, hour) cells, or ``None`` for unrestricted.
        Occupied cells keep their occupied tint.
        """
        for r, hour in enumerate(HOURS):
            for c in range(len(DAYS)):
                item = self.item(r, c)
                if item is None or item.text():
                    continue  # leave occupied cells as-is
                if allowed is None:
                    item.setBackground(QBrush(Qt.GlobalColor.transparent))
                elif (c, hour) in allowed:
                    item.setBackground(QBrush(_ALLOWED_BRUSH))
                else:
                    item.setBackground(QBrush(_BLOCKED_BRUSH))

    # -------------------------------------------------------------- drag/drop
    @staticmethod
    def _has_payload(event) -> bool:
        return event.mimeData().hasFormat(ENTITY_MIME_TYPE)

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        """Begin an internal drag to move an existing lesson to another cell."""
        item = self.currentItem()
        if item is None:
            return
        day, hour = item.column(), HOURS[item.row()]
        slot = self._slots.get((day, hour))
        if slot is None:
            return  # only occupied cells can be moved
        payload = f"{slot.entity_type}:{slot.entity_id}".encode("utf-8")
        mime = QMimeData()
        mime.setData(ENTITY_MIME_TYPE, QByteArray(payload))
        drag = QDrag(self)
        drag.setMimeData(mime)
        self._move_source = (day, hour)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._move_source = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Delete the selected lesson with the Delete/Backspace key."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            item = self.currentItem()
            if item is not None:
                cell = (item.column(), HOURS[item.row()])
                if cell in self._slots:
                    self.unassignRequested.emit(cell[0], cell[1])
                    return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._has_payload(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._has_payload(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if not self._has_payload(event):
            event.ignore()
            return
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        if item is None:
            event.ignore()
            return

        day = item.column()
        hour = HOURS[item.row()]

        # Internal move: a lesson dragged from another cell of this grid.
        if self._move_source is not None:
            src_day, src_hour = self._move_source
            event.acceptProposedAction()
            if (src_day, src_hour) != (day, hour):
                self.moveRequested.emit(src_day, src_hour, day, hour)
            return

        raw = bytes(event.mimeData().data(ENTITY_MIME_TYPE)).decode("utf-8")
        entity_type, _, id_text = raw.partition(":")
        try:
            entity_id = int(id_text)
        except ValueError:
            event.ignore()
            return

        event.acceptProposedAction()
        self.entityDropped.emit(day, hour, entity_type, entity_id)

    # -------------------------------------------------------------- context
    def _on_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None or not item.text():
            return
        menu = QMenu(self)
        remove_action = menu.addAction("ביטול שיבוץ")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == remove_action:
            self.unassignRequested.emit(item.column(), HOURS[item.row()])
