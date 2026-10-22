ETHERMOTION IN THE UALR DEMO

The demo includes a documentation subset from YeChamo/EtherMotion.
EtherMotion is a separate installation. The UALR demo
uses its local HTTP interface to request an existing saved Once divert cycle.

Full source, tests, build instructions, and complete documentation are in:
https://github.com/YeChamo/EtherMotion

That repository is private; access requires authorization from its owner.
The bundled README.md, QUICKSTART.txt, and TRIGGERS.md describe the full
EtherMotion distribution and may refer to files outside this demo subset.
This folder does not contain EtherMotion's complete source or build recipe.
The public Git source and Windows release do not redistribute the separate
EtherMotion executable. Use an authorized existing EtherMotion installation.
The app checks %USERPROFILE%\Desktop\EtherMotion\EtherMotion.exe, then this
folder as an optional fallback.

UALR-simulator-workspace.json is example configuration for an isolated
simulator. It contains no physical driver, saved machine position, or trigger
token. Start EtherMotion Simulator.cmd creates its writable local workspace
under data/ethermotion-simulator and starts that service on port 8766.

See ../docs/ETHERMOTION_SETUP.txt for the UALR connection and timing setup.
This provenance note does not assign a license to EtherMotion.
