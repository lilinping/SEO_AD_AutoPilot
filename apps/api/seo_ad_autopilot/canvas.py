"""Canvas visualization system.

Inspired by OpenClaw's Canvas:
- Real-time visualization of analysis results
- Interactive charts and graphs
- Export to image/PDF
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class CanvasWidget:
    """A widget on the canvas."""
    widget_id: str
    widget_type: str  # chart, table, text, image
    title: str
    data: dict[str, Any] = field(default_factory=dict)
    position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    size: dict[str, int] = field(default_factory=lambda: {"width": 400, "height": 300})


@dataclass
class CanvasState:
    """Canvas state."""
    canvas_id: str
    widgets: list[CanvasWidget] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class CanvasManager:
    """Manage canvas visualizations."""
    
    def __init__(self):
        self._canvases: dict[str, CanvasState] = {}
    
    def create_canvas(self, canvas_id: str) -> CanvasState:
        """Create a new canvas."""
        canvas = CanvasState(canvas_id=canvas_id)
        self._canvases[canvas_id] = canvas
        return canvas
    
    def get_canvas(self, canvas_id: str) -> Optional[CanvasState]:
        """Get a canvas by ID."""
        return self._canvases.get(canvas_id)
    
    def add_widget(
        self,
        canvas_id: str,
        widget_type: str,
        title: str,
        data: dict[str, Any],
        position: Optional[dict[str, int]] = None,
        size: Optional[dict[str, int]] = None,
    ) -> Optional[CanvasWidget]:
        """Add a widget to the canvas."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return None
        
        widget = CanvasWidget(
            widget_id=f"widget_{len(canvas.widgets)}",
            widget_type=widget_type,
            title=title,
            data=data,
            position=position or {"x": 0, "y": len(canvas.widgets) * 320},
            size=size or {"width": 400, "height": 300},
        )
        
        canvas.widgets.append(widget)
        canvas.updated_at = datetime.now()
        
        return widget
    
    def create_analysis_dashboard(self, analysis_data: dict[str, Any]) -> CanvasState:
        """Create a dashboard canvas from analysis results."""
        canvas_id = f"dashboard_{uuid.uuid4().hex[:8]}"
        canvas = self.create_canvas(canvas_id)
        
        # GEO Score chart
        geo_scores = analysis_data.get("geo_scores", {})
        self.add_widget(
            canvas_id,
            "chart",
            "GEO Scores",
            {
                "type": "radar",
                "labels": ["Citation", "Entity", "Structure", "Authority", "AI Presence"],
                "values": [
                    geo_scores.get("citation", 0),
                    geo_scores.get("entity", 0),
                    geo_scores.get("structure", 0),
                    geo_scores.get("authority", 0),
                    geo_scores.get("ai_presence", 0),
                ],
            },
        )
        
        # Ad Readiness gauge
        ad_readiness = analysis_data.get("ad_readiness", {})
        self.add_widget(
            canvas_id,
            "gauge",
            "Ad Readiness",
            {
                "value": ad_readiness.get("score", 0),
                "max": 100,
                "grade": ad_readiness.get("grade", "N/A"),
            },
        )
        
        # Recommendations list
        recommendations = analysis_data.get("recommendations", [])
        self.add_widget(
            canvas_id,
            "list",
            "Recommendations",
            {
                "items": [
                    {"title": r.get("title", ""), "priority": r.get("priority", "medium")}
                    for r in recommendations[:5]
                ],
            },
        )
        
        # Search Results table
        search_results = analysis_data.get("search_results", [])
        self.add_widget(
            canvas_id,
            "table",
            "Search Results",
            {
                "columns": ["Engine", "Position", "Title"],
                "rows": [
                    [r.get("engine", ""), r.get("position", 0), r.get("title", "")]
                    for r in search_results[:5]
                ],
            },
        )
        
        return canvas
    
    def export_to_html(self, canvas_id: str) -> str:
        """Export canvas to HTML."""
        canvas = self._canvases.get(canvas_id)
        if not canvas:
            return ""
        
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head><title>Analysis Dashboard</title>",
            "<style>",
            "body{font-family:sans-serif;margin:20px;}",
            ".widget{border:1px solid #ccc;border-radius:8px;padding:16px;margin:10px;}",
            ".widget h3{margin-top:0;}",
            ".chart{background:#f5f5f5;}",
            ".gauge{text-align:center;}",
            ".gauge .value{font-size:48px;font-weight:bold;}",
            ".list ul{padding-left:20px;}",
            ".table table{width:100%;border-collapse:collapse;}",
            ".table th,.table td{border:1px solid #ddd;padding:8px;text-align:left;}",
            "</style>",
            "</head><body>",
            f"<h1>Analysis Dashboard</h1>",
            f"<p>Canvas ID: {canvas.canvas_id}</p>",
            f"<p>Generated: {canvas.updated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
        ]
        
        for widget in canvas.widgets:
            html_parts.append(f'<div class="widget {widget.widget_type}">')
            html_parts.append(f"<h3>{widget.title}</h3>")
            
            if widget.widget_type == "chart":
                html_parts.append(self._render_chart_html(widget.data))
            elif widget.widget_type == "gauge":
                html_parts.append(self._render_gauge_html(widget.data))
            elif widget.widget_type == "list":
                html_parts.append(self._render_list_html(widget.data))
            elif widget.widget_type == "table":
                html_parts.append(self._render_table_html(widget.data))
            
            html_parts.append("</div>")
        
        html_parts.append("</body></html>")
        return "\n".join(html_parts)
    
    def _render_chart_html(self, data: dict[str, Any]) -> str:
        """Render chart widget as HTML."""
        chart_type = data.get("type", "bar")
        labels = data.get("labels", [])
        values = data.get("values", [])
        
        if chart_type == "radar":
            # Simple text representation
            lines = []
            for label, value in zip(labels, values):
                bar = "█" * (value // 5)
                lines.append(f"<div>{label}: {bar} {value}</div>")
            return "\n".join(lines)
        return "<p>Chart visualization</p>"
    
    def _render_gauge_html(self, data: dict[str, Any]) -> str:
        """Render gauge widget as HTML."""
        value = data.get("value", 0)
        grade = data.get("grade", "N/A")
        return f"""
        <div class="value">{value:.0f}</div>
        <div>Grade: {grade}</div>
        <div style="background:#eee;height:20px;border-radius:10px;overflow:hidden;">
            <div style="background:#4CAF50;height:100%;width:{value}%;"></div>
        </div>
        """
    
    def _render_list_html(self, data: dict[str, Any]) -> str:
        """Render list widget as HTML."""
        items = data.get("items", [])
        if not items:
            return "<p>No items</p>"
        
        html = "<ul>"
        for item in items:
            priority_color = {"high": "red", "medium": "orange", "low": "green"}.get(
                item.get("priority", "medium"), "gray"
            )
            html += f'<li><span style="color:{priority_color}">●</span> {item.get("title", "")}</li>'
        html += "</ul>"
        return html
    
    def _render_table_html(self, data: dict[str, Any]) -> str:
        """Render table widget as HTML."""
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        if not columns:
            return "<p>No data</p>"
        
        html = "<table><thead><tr>"
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"
        
        for row in rows:
            html += "<tr>"
            for cell in row:
                html += f"<td>{cell}</td>"
            html += "</tr>"
        
        html += "</tbody></table>"
        return html
