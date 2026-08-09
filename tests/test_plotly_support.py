from plotly_support import PLOTLY_CONFIG


def test_plotly_config_preserves_required_interactions():
    assert PLOTLY_CONFIG["displayModeBar"] is True
    assert PLOTLY_CONFIG["modeBarButtons"] == [["zoom2d", "pan2d", "resetScale2d"]]
    assert PLOTLY_CONFIG["responsive"] is True
    assert PLOTLY_CONFIG["scrollZoom"] is True
