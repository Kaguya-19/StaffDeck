# @staffdeck/business-ui

This package is the versioned source of the StaffDeck business surfaces that
are consumed by both StaffDeck and PilotDeck. It owns business interaction and
rendering while each host supplies an adapter for transport, auth context,
notifications, navigation, and localized labels.

The package currently exports the original Knowledge graph slice and the
original StaffDeck SOP version-detail dialog slice. The full Knowledge and SOP
pages remain owned by StaffDeck until their original formal UI and state can
be extracted without replacing them with a new workbench. PilotDeck vendors
the exact `0.1.0` release under its composition module tree; it does not
import a StaffDeck checkout or maintain a second implementation.
