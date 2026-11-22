# Security reporting

Report vulnerabilities through this repository's GitHub private vulnerability
reporting feature when available, or email Dutchman CAD at
[hello@dutchmancad.xyz](mailto:hello@dutchmancad.xyz). Avoid posting confidential details,
CAD files, credentials, or exploit code. Maintainers should acknowledge security
reports promptly, coordinate a fix, and publish a GitHub security advisory with
affected versions, upgrade instructions, and any local mitigation required.

Security fixes should cover affected supported releases. Version 0.1.x is the
initial supported series. Keep Dutchman and FreeCAD updated separately as well.

The installed Dutchman executable produces Python code executed with FreeCAD's
permissions. Install executables only from sources you trust. Optional release
installation verifies the archive checksum supplied by the same upstream
release; it does not provide an independent publisher signature. Temporary
conversion files are private and are removed after execution. The addon does
not install Python packages or expose a network listener.
