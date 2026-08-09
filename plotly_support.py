from functools import cache

from plotly.offline import get_plotlyjs

PLOTLY_CONFIG: dict[str, object] = {
    "displaylogo": False,
    "displayModeBar": True,
    "modeBarButtons": [["zoom2d", "pan2d", "resetScale2d"]],
    "responsive": True,
    "scrollZoom": True,
    "showTips": False,
}


@cache
def plotly_javascript() -> str:
    return get_plotlyjs()
