# Data and external connections

The addon passes the selected source file's path to your installed Dutchman
executable and reads its generated macro and JSON report locally. The addon
itself does not upload CAD files, source paths, object names, dimensions,
conversion reports, or screenshots. The separate executable's behavior is covered
by its own documentation and policies.

The addon makes release requests only when Dutchman is missing, automatic downloads are
enabled in preferences, and you accept the download confirmation for that import.
There are no periodic update requests. Startup discovers formats by running the
local executable; it does not contact the release service or install software.

The release installer requests public release metadata from `api.github.com`
and checksums and a selected OS/architecture archive from GitHub release URLs.
GitHub may redirect archive requests to its download infrastructure. Those
services receive your IP address, a `Dutchman-FreeCAD/0.1.6` user agent, and the
requested URLs, which identify the selected release and platform archive. Your
system's configured HTTP proxy, if any, may also observe these requests.
No account, access token, or saved credentials are requested or used by the addon.

Opening a documentation, Discord, or GitHub link launches your browser. The
browser contacts the selected site using its normal network and account settings.
The addon does not attach CAD files or conversion reports to these links. Review
anything you choose to share; Discord DMs to Dutchy are private, while GitHub
issues are public.

Preferences store the executable path, download setting, and optional output
folder in FreeCAD's user parameter store. The optional managed executable is
stored under `Dutchman/bin` in the user data directory. Conversion uses a private
system temporary directory removed after completion or failure. Requested FCStd
copies are written to the folder you choose; choose a folder with access controls
appropriate for your documents. The report remains visible in the dock or console
until you close it or another import replaces it.

Turning off automatic downloads prevents future release requests. To remove local
settings or the managed executable, close FreeCAD and remove the corresponding
Dutchman preferences or user-data directory. This does not delete copies you
chose to save. Changes to external services or categories of data sent must be
disclosed here and in the in-app confirmation before requesting new consent.
