"""Sidebar listing schedulable entities; acts as a drag source."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDrag
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from app.config import ENTITY_MIME_TYPE
from app.controllers.schedule_controller import EntityInfo

_ROLE_TYPE = Qt.ItemDataRole.UserRole
_ROLE_ID = Qt.ItemDataRole.UserRole + 1
_ROLE_ASSIGNABLE = Qt.ItemDataRole.UserRole + 2

_UNQUALIFIED_COLOR = QColor("#d64545")


class EntitySidebar(QListWidget):
    """A drag-enabled list of students and study groups."""

    entitySelected = Signal(str, int)  # (entity_type, entity_id)
    selectionCleared = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setWordWrap(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_entities(self, entities: list[EntityInfo]) -> None:
        self.clear()
        for entity in entities:
            if entity.required_hours is None:
                progress = f"שובץ {entity.scheduled_count} (ידני)"
            else:
                progress = f"שובץ {entity.scheduled_count}/{entity.required_hours}"
            text = f"{entity.label}\n[{entity.subject_name}] · {progress}"
            if entity.preferred_tutor_name:
                text += f"\n(חונכת מועדפת: {entity.preferred_tutor_name})"
            item = QListWidgetItem(text)
            item.setData(_ROLE_TYPE, entity.entity_type)
            item.setData(_ROLE_ID, entity.entity_id)
            item.setData(_ROLE_ASSIGNABLE, entity.assignable)

            fully_scheduled = (
                entity.required_hours is not None
                and entity.scheduled_count >= entity.required_hours
            )

            if fully_scheduled:
                item.setForeground(Qt.GlobalColor.gray)
            elif not entity.assignable:
                item.setForeground(QBrush(_UNQUALIFIED_COLOR))
                item.setToolTip(
                    f"החונכת הנבחרת אינה מוסמכת ל{entity.subject_name}"
                )
                flags = item.flags()
                flags &= ~Qt.ItemFlag.ItemIsDragEnabled
                item.setFlags(flags)
            self.addItem(item)

    def _on_selection_changed(self) -> None:
        item = self.currentItem()
        if item is None:
            self.selectionCleared.emit()
            return
        self.entitySelected.emit(
            str(item.data(_ROLE_TYPE)), int(item.data(_ROLE_ID))
        )

    def startDrag(self, supported_actions) -> None:  # noqa: N802 (Qt override)
        item = self.currentItem()
        if item is None:
            return
        if item.data(_ROLE_ASSIGNABLE) is False:
            return

        entity_type = str(item.data(_ROLE_TYPE))
        entity_id = int(item.data(_ROLE_ID))

        mime = QMimeData()
        payload = f"{entity_type}:{entity_id}".encode("utf-8")
        mime.setData(ENTITY_MIME_TYPE, payload)

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
