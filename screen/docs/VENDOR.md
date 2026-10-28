# Bundled viewer provenance

The bundled noVNC viewer matches upstream v1.7.0 at its RFB entry point and display module. These checks identify the source version; they do not certify every vendored file as unmodified.

- Source: https://github.com/novnc/noVNC/tree/v1.7.0
- MPL 2.0 license and original authors: `dashboard/dist/vendor/novnc/LICENSE.txt` and `AUTHORS`.
- Included pako license remains at `dashboard/dist/vendor/novnc/vendor/pako/LICENSE`.

Keep these notices and corresponding source provenance when packaging or bundling the viewer. No CDN dependency is required.
