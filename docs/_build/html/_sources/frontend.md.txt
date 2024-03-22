# Web UI
A [Streamlit](https://streamlit.io) frontend can be run via:

```sh
git clone https://github.com/mit-ll/qrdm
cd qrdm
python -m pip install .[frontend]
streamlit run ui/QRDM_Home.py --client.toolbarMode=viewer
```

This will host the app at `http://localhost:8501` by default, with pages for QR encoding
and decoding. The host and port can be controlled by passing `--server.port=XXXX` and
`--server.address=X.X.X.X`, as per the syntax of the `streamlit run` command.

:::{image} _static/streamlit-ui.png
:alt: Screenshot of a browser window, showing the QRDM Web UI served by Streamlit.
:::